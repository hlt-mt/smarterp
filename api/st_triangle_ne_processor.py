# Copyright 2022 FBK

# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at

#     http://www.apache.org/licenses/LICENSE-2.0

# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License
import json
import os
import re
import requests
import string
from typing import List, Optional, Tuple

from dataclasses import dataclass
from thefuzz import fuzz, process
import text_to_num

from api.st_triangle_processor import STTriangleProcessorResponse, STTriangleProcessor, STTriangleProcessorRequest
from api.misc import stopwords


REMOVE_NE_PATTERN = re.compile(r'</?[A-Z_]+>')
NE_PATTERN = re.compile(r"<(.+)>([^<]+)</\1>")
LINKEDDATA_URL = f'http://{os.getenv("LINKEDDATA_IP", "3.121.98.219")}/api/'


def translate_langcode(iso):
    if iso == "es":
        return "SPA"
    if iso == "en":
        return "ENG"
    if iso == "fr":
        return "FRA"
    if iso == "it":
        return "ITA"
    if iso == "de":
        return "GER"


def ne_from_output(line):
    all_matches = NE_PATTERN.findall(line)
    entities = []
    for entity_type, entity_content in all_matches:
        entities.append((entity_content, entity_type))
    return entities


def flatten(ll):
    out = []
    for l in ll:
        out.extend(l)
    return out


def stopwords_by_lang(iso):
    if iso == "es":
        return stopwords.spanish
    if iso == "en":
        return stopwords.english
    if iso == "fr":
        return stopwords.french


def clean_stopwords(text, lang):
    for sw in stopwords_by_lang(lang):
        if text.startswith(sw + ' '):
            text = text[len(sw) + 1:].strip()
    return text


def extract_ne(text, srclang, tgtlang):
    kg_server_response = requests.post(
        LINKEDDATA_URL,
        data={
            'lang_in': translate_langcode(srclang),
            'lang_out': translate_langcode(tgtlang),
            'query': REMOVE_NE_PATTERN.sub('', text).replace("-", " ").replace("'", " ").strip()})
    assert 199 < kg_server_response.status_code < 300, \
        f"{LINKEDDATA_URL} responded {kg_server_response.status_code}: {kg_server_response.text}"
    wikidata = json.loads(kg_server_response.text)["result"]
    if "translations" in wikidata:
        wikidata = wikidata["translations"]
    else:
        wikidata = {}
    result = []
    for ne in ne_from_output(text):
        ids = set()
        for k in wikidata.keys():
            if k in ne[0]:
                for e in wikidata[k]:
                    ids.add(e["uri"].split("/")[-1])
        wiki_trans = None
        if 'cientos' in ne[0] or 'centaines' in ne[0]:
            ids.add('FN100')
        if 'millions' in ne[0] or 'millones' in ne[0]:
            ids.add('FN1000000')
        if ne[0] in wikidata:
            wiki_trans = flatten([
                t["translation"][translate_langcode(tgtlang)]
                for t in wikidata[ne[0]] if translate_langcode(tgtlang) in t["translation"]])
        else:
            cleaned_ne = clean_stopwords(ne[0], srclang)
            if cleaned_ne in wikidata:
                wiki_trans = flatten([
                    t["translation"][translate_langcode(tgtlang)]
                    for t in wikidata[cleaned_ne] if translate_langcode(tgtlang) in t["translation"]])
            if ne[0] == 'Africa occidental':
                wiki_trans = ["Afrique de l'ouest"]
            if ne[0] == 'cuarenta y cinco':
                wiki_trans = ["quarante cinq"]
        result.append((ne[0], ne[1], ids, wiki_trans))
    return result


def possible_matches(substring, full_string):
    num_tokens = len(substring.split())
    string_tokens = full_string.strip().split()
    return [
        " ".join(string_tokens[i:i + num_tokens])
        for i in range(len(string_tokens) - num_tokens + 1)
    ]


def do_exact_match(substring, full_string):
    all_substrings = possible_matches(substring, REMOVE_NE_PATTERN.sub('', full_string))
    try:
        idx = [s.lower() for s in all_substrings].index(substring.lower())
        return all_substrings[idx]
    except ValueError:
        try:
            idx = [s.lower().strip("l'").strip("d'").translate(str.maketrans('', '', string.punctuation + "—")) for s in all_substrings].index(substring.lower().translate(str.maketrans('', '', string.punctuation + "—")))
            return all_substrings[idx]
        except ValueError:
            return None


def do_fuzzy_match(substring, full_string):
    all_substrings = possible_matches(substring, full_string)
    match = process.extractOne(substring, all_substrings, scorer=fuzz.token_sort_ratio, score_cutoff=0.6)
    if match is not None:
        return match[0]
    else:
        return None


def extract_nes(transcript, translation, slang, tlang, logger):
    ne_transcript = extract_ne(transcript, slang, tlang)
    ne_translation = extract_ne(translation, tlang, slang)
    to_be_aligned = []
    paired = []
    for (e, etype, eids, etrans) in ne_translation:
        if etrans is None:
            etrans = [e]
        current = None
        max_common = 0
        for (se, setype, seids, setrans) in ne_transcript:
            common_ids = len(eids.intersection(seids))
            if common_ids > 0 and common_ids > max_common:
                current = (se, setype, seids, setrans)
                max_common = common_ids
        if current is None:
            for (se, setype, seids, setrans) in ne_transcript:
                for t in etrans:
                    if t.lower() == se.lower():
                        current = (se, setype, seids, setrans)

        if current is not None:
            ne_transcript.remove(current)

        if current is None:
            for t in etrans:
                match = do_exact_match(t, transcript)
                if match is not None:
                    current = (match, etype, eids, e)
                    break

        if current is None:
            to_be_aligned.append((e, etype, eids, etrans))
        else:
            paired.append((current[0], e, etype))

    # Align remaining NE by type
    for (e, etype, eids, etrans) in to_be_aligned:
        same_type = []
        for (se, setype, seids, setrans) in ne_transcript:
            if setype == etype:
                same_type.append((se, setype, seids, setrans))
        if len(same_type) == 1:
            paired.append((same_type[0][0], e, etype))
        elif etype == "PERSON" and len(eids) > 0:
            match = do_fuzzy_match(e, transcript)
            if match:
                paired.append((match, e, etype))
            else:
                logger.debug(f"Issue pairing {(e, etype, eids, etrans)}.\n We were pairing: {ne_transcript}")
        elif etype == "CARDINAL":
            match = process.extractOne(
                e,
                [se for (se, setype, _, _) in ne_transcript if setype == "CARDINAL"],
                scorer=fuzz.token_sort_ratio,
                score_cutoff=0.6)
            if match is not None:
                paired.append((e, match[0], etype))
            else:
                logger.debug(f"Issue pairing {(e, etype, eids, etrans)}.\n We were pairing: {ne_transcript}")
        else:
            logger.debug(f"Issue pairing {(e, etype, eids, etrans)}.\n We were pairing: {ne_transcript}")
    return paired


def extract_terms_from_source(transcript, translation, terms_dict, logger) -> List[Tuple[str, str]]:
    transcript = REMOVE_NE_PATTERN.sub('', transcript)
    transcript_lc = transcript.lower()
    found = []
    for entry in terms_dict:
        s, ts = entry
        if s in transcript_lc:
            idx = transcript_lc.index(s)
            end_of_term = len(re.split(r'\W+', transcript[idx + len(s):])[0])
            start_of_term = len(re.split(r'\W+', transcript[:idx][::-1])[0])
            term = transcript[idx - start_of_term:idx + len(s) + end_of_term]
            if fuzz.WRatio(term, s) < 0.8:
                continue
            found.append((s, ts[0]))
    return found


def extract_terms(transcript, translation, terms_dict, logger) -> List[Tuple[str, str]]:
    transcript = REMOVE_NE_PATTERN.sub('', transcript)
    translation = REMOVE_NE_PATTERN.sub('', translation)
    transcript_lc = transcript.lower()
    translation_lc = translation.lower()
    found = []
    for entry in terms_dict:
        s, ts = entry
        if s in transcript_lc:
            idx = transcript_lc.index(s)
            end_of_term = len(re.split(r'\W+', transcript[idx + len(s):])[0])
            start_of_term = len(re.split(r'\W+', transcript[:idx][::-1])[0])
            term = transcript[idx - start_of_term:idx + len(s) + end_of_term]
            if fuzz.WRatio(term, s) < 0.8:
                continue
            tgt_found = False
            for t in ts:
                if t in translation_lc:
                    found.append((s, t))
                    tgt_found = True
                    break
            if not tgt_found:
                logger.debug(f"Cannot pair {term} ({s}) - {ts} in {transcript} -- {translation}")
    return found


@dataclass
class STTriangleNEProcessorRequest(STTriangleProcessorRequest):
    dictionary: Optional[str] = None


@dataclass
class STTriangleNEProcessorResponse(STTriangleProcessorResponse):
    nes: List[Tuple[str, str, str]]
    terms: List[Tuple[str, str]]


class STTriangleNEProcessor(STTriangleProcessor):
    request_class = STTriangleNEProcessorRequest
    LOADED_DICTS = {}
    supported_langs = {"es", "fr", "en"}

    def __init__(self, cfg):
        super().__init__(cfg)
        self.extract_terms_from_transcript_only = int(os.getenv('EXTRACT_TERMS_FROM_TRANSCRIPT', 1)) == 1
        self.alpha2digit_conversion = int(os.getenv('CONVERT_ALPHA2DIGITS', 1)) == 1
        for lang in self.supported_langs:
            parser = text_to_num.lang.LANG[lang]
            for m in parser.MULTIPLIERS:
                if m not in {"thousand", "thousands", "mil", "mille", "milles", "miles"}:
                    parser.NUMBERS.pop(m)
        text_to_num.lang.LANG["es"].DECIMAL_SEP = "punto"

    @staticmethod
    def ne_digit_converter(nes, slang, tlang):
        return [
            (text_to_num.alpha2digit(ne[0], lang=slang), text_to_num.alpha2digit(ne[1], lang=tlang), ne[2])
            for ne in nes
        ]

    @staticmethod
    def remove_stopwords(nes, slang, tlang):
        for i in range(len(nes)):
            if len(nes[i]) == 2:
                new_ne = (clean_stopwords(nes[i][0], slang), clean_stopwords(nes[i][1], tlang))
            else:
                new_ne = (clean_stopwords(nes[i][0], slang), clean_stopwords(nes[i][1], tlang), nes[i][2])
            nes[i] = new_ne
        return nes

    def load_dict(self, dict_fn):
        if dict_fn not in self.LOADED_DICTS:
            new_dict = []
            with open(dict_fn) as f:
                for line in f:
                    t = line.strip().split("\t")
                    new_dict.append((t[0].lower(), list(map(lambda x: x.lower(), t[1].split(",")))))
            self.LOADED_DICTS[dict_fn] = new_dict
        return self.LOADED_DICTS[dict_fn]

    def _postproc(self, request_id, hypo, request: STTriangleNEProcessorRequest):
        st_triangle_response = super()._postproc(request_id, hypo, request)
        nes = extract_nes(
            st_triangle_response.transcript,
            st_triangle_response.translation,
            request.src_lang,
            request.tgt_lang,
            self.logger)
        if request.dictionary is not None:
            terms_dict = self.load_dict(request.dictionary)
            fn_extract_terms = extract_terms_from_source if self.extract_terms_from_transcript_only else extract_terms
            terms = fn_extract_terms(
                st_triangle_response.transcript,
                st_triangle_response.translation,
                terms_dict,
                self.logger)
        else:
            terms = []

        if self.alpha2digit_conversion:
            nes = self.ne_digit_converter(nes, request.src_lang, request.tgt_lang)

        return STTriangleNEProcessorResponse(
            st_triangle_response.score,
            st_triangle_response.translation,
            st_triangle_response.transcript,
            self.remove_stopwords(nes, request.src_lang, request.tgt_lang),
            self.remove_stopwords(terms, request.src_lang, request.tgt_lang))
