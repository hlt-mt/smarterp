# Copyright 2021 FBK

# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at

#     http://www.apache.org/licenses/LICENSE-2.0

# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License
from examples.speech_to_text.models.base_triangle import BaseTriangle
from examples.speech_to_text.models.conformer import ConformerModel, conformer_base_architecture, conformer_s

from fairseq.models import register_model, register_model_architecture


@register_model('conformer_triangle')
class ConformerTriangle(BaseTriangle):
    encoder_parent_model = ConformerModel

    @staticmethod
    def add_args(parser):
        BaseTriangle.add_args(parser)
        ConformerModel.add_args(parser)

    @staticmethod
    def add_base_args(args):
        base_conformer_triangle_architecture(args)


@register_model_architecture('conformer_triangle', 'conformer_triangle')
def base_conformer_triangle_architecture(args):
    conformer_base_architecture(args)


@register_model_architecture('conformer_triangle', 'conformer_triangle_s')
def conformer_triangle_s(args):
    conformer_s(args)
