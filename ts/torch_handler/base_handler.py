

"""
Base default handler to load torchscript or eager mode [state_dict] models
Also, provides handle method per torch serve custom model specification
"""
import abc
import logging
import os
import json

import torch

logger = logging.getLogger(__name__)


class BaseHandler(abc.ABC):
    def __init__(self):
        self.model = None
        self.mapping = None
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        self.initialized = False

    def initialize(self, ctx):
        """First try to load torchscript else load eager mode state_dict based model"""

        properties = ctx.system_properties
        model_dir = properties.get("model_dir")

        # Read model serialize/pt file
        model_pt_path = os.path.join(model_dir, "model.pt")
        if not os.path.isfile(model_pt_path):
            raise RuntimeError("Missing the model.pt file")

        try:
            logger.debug('Loading torchscript model')
            self.model = torch.jit.load(model_pt_path)
        except Exception as e:
            # Read model definition file
            model_def_path = os.path.join(model_dir, "model.py")
            if not os.path.isfile(model_def_path):
                raise RuntimeError("Missing the model.py file")

            import importlib
            from ..utils.util import list_classes_from_module

            module = importlib.import_module('model')
            model_class_definitions = list_classes_from_module(module)
            if len(model_class_definitions) != 1:
                raise ValueError("Expected only one class as model definition. {}".format(
                    model_class_definitions))

            model_class = model_class_definitions[0]
            state_dict = torch.load(model_pt_path, map_location=self.device)
            self.model = model_class()
            self.model.load_state_dict(state_dict)

        logger.debug('Model file {0} loaded successfully'.format(model_pt_path))

        # Read the mapping file, index to object name
        mapping_file_path = os.path.join(model_dir, "index_to_name.json")

        if os.path.isfile(mapping_file_path):
            with open(mapping_file_path) as f:
                self.mapping = json.load(f)
        else:
            logger.warning('Missing the index_to_name.json file. Inference output will not include class name.')

        self.initialized = True

    @abc.abstractmethod
    def preprocess(self, data):
        pass

    @abc.abstractmethod
    def inference(self, data):
        pass

    @abc.abstractmethod
    def postprocess(self, data):
        pass
