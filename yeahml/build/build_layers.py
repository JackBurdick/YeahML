import tensorflow as tf
import numpy as np
from typing import Any, List
from yeahml.build.components.activation import get_activation_fn
from yeahml.log.yf_logging import config_logger  # custom logging

from yeahml.helper import fmt_tensor_info

from yeahml.build.layers.recurrent import build_recurrent_layer
from yeahml.build.get_components import get_initializer_fn
from yeahml.build.layers.config import return_available_layers
from yeahml.build.layers.other import (
    build_embedding_layer,
    build_batch_normalization_layer,
)

from yeahml.build.components.regularizer import get_regularizer_fn
from yeahml.build.components.config import return_activation


def _configure_activation(opt_dict):
    # TODO: this is dangerous.... (updating the __defaults__ like this)
    act_fn = return_activation(opt_dict["type"])["function"]
    temp_copy = opt_dict.copy()
    _ = temp_copy.pop("type")
    if temp_copy:
        var_list = list(act_fn.__code__.co_varnames)
        cur_defaults_list = list(act_fn.__defaults__)
        # TODO: try?
        var_list.remove("x")
        for ao, v in temp_copy.items():
            arg_index = var_list.index(ao)
            # TODO: same type assertion?
            cur_defaults_list[arg_index] = v

    return act_fn


def build_layer(ltype, opts, l_name, logger, g_logger):

    # TODO: could place a ltype = get_ltype_mapping() here
    LAYER_FUNCTIONS = return_available_layers()
    if ltype in LAYER_FUNCTIONS.keys():
        func = LAYER_FUNCTIONS[ltype]["function"]
        try:
            func_args = LAYER_FUNCTIONS[ltype]["func_args"]
            opts.update(func_args)
        except KeyError:
            pass

        # TODO: name should be set earlier, as an opts?
        logger.debug(f"-> START building: {l_name}")
        if opts:
            # TODO: encapsulate this logic, expand as needed
            # could also implement a check upfront to see if the option is valid
            for o in opts:
                if o == "kernel_regularizer":
                    opts[o] = get_regularizer_fn(opts[o])
                elif o == "activation":
                    opts[o] = _configure_activation(opts[o])
                elif o == "kernel_initializer":
                    opts[o] = get_initializer_fn(opts[o])
                elif o == "bias_initializer":
                    opts[o] = get_initializer_fn(opts[o])
            cur_layer = func(**opts, name=l_name)
        else:
            cur_layer = func(name=l_name)
        g_logger.info(f"{fmt_tensor_info(cur_layer)}")

    return cur_layer


def build_hidden_block(MCd: dict, HCd: dict, logger, g_logger) -> List[Any]:
    logger.info("-> START building hidden block")
    HIDDEN_LAYERS = []

    # build each layer based on the (ordered) yaml specification
    logger.debug(f"loop+start building layers: {HCd['layers'].keys()}")
    for i, l_name in enumerate(HCd["layers"]):
        layer_info = HCd["layers"][str(l_name)]
        opts = layer_info["options"]
        # # print(opts)
        # try:
        #     activation = get_activation_fn(layer_info["activation"])
        # except KeyError:
        #     pass

        ltype = layer_info["type"].lower()
        logger.debug(f"-> START building: {l_name} ({ltype}) opts: {layer_info}")
        cur_layer = build_layer(ltype, opts, l_name, logger, g_logger)
        logger.debug(f"[End] building: {cur_layer}")

        # elif ltype == "embedding":
        #     cur_layer = build_embedding_layer(opts, l_name, logger, g_logger)
        # elif ltype == "batch_normalization":
        #     cur_layer = build_batch_normalization_layer(opts, l_name, logger, g_logger)
        # elif ltype == "recurrent":
        #     cur_layer = build_recurrent_layer(opts, actfn, l_name, logger, g_logger)
        # else:
        #     raise NotImplementedError(f"layer type: {ltype} not implemented yet")

        HIDDEN_LAYERS.append(cur_layer)

    logger.info("[END] building hidden block")

    # opt = return_activation("relu")
    # print(opt)
    # sys.exit()
    return HIDDEN_LAYERS
