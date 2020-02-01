from datetime import datetime

from yeahml.build.components.activation import _configure_activation
from yeahml.build.components.constraint import _configure_constraint
from yeahml.build.components.initializer import _configure_initializer
from yeahml.build.components.regularizer import _configure_regularizer
from yeahml.build.layers.config import return_available_layers
from yeahml.build.layers.other import (
    build_batch_normalization_layer,
    build_embedding_layer,
)
from yeahml.helper import fmt_tensor_info


def log_and_time_layer_build(func):
    def function_wrapper(*args, **kwargs):

        # TODO: this is currently hardcoded and dangerous.. are kwargs the answer?
        ltype = args[0]
        opts = args[1]
        l_name = args[2]
        logger = args[3]
        g_logger = args[4]

        logger.debug(
            f"START ({func.__name__}):  {l_name} type:({ltype}), opts:({opts})"
        )
        start_time = datetime.now()
        out = func(*args, **kwargs)
        end_time = datetime.now()
        logger.debug(
            f"[End] ({func.__name__}): {l_name} - build duration: ({(end_time - start_time).total_seconds()})"
        )
        g_logger.info(f"{fmt_tensor_info(out)}")

        return out

    return function_wrapper


@log_and_time_layer_build
def build_layer(ltype, opts, l_name, logger, g_logger):

    # NOTE: this is fairly hacky and the logic of this function could be rethought
    # a bit - the issue is that without the opts.copy() we end up overwritting
    # values within the dict, which may cause issues downstream

    if opts:
        functional_opts = opts.copy()
    # TODO: could place a ltype = get_ltype_mapping() here
    # NOTE: this in LAYER_FUNCTIONS.keys() is a check that should already
    # be caught when creating the config
    LAYER_FUNCTIONS = return_available_layers()
    if ltype in LAYER_FUNCTIONS.keys():
        func = LAYER_FUNCTIONS[ltype]["function"]
        try:
            func_args = LAYER_FUNCTIONS[ltype]["func_args"]
            functional_opts.update(func_args)
        except KeyError:
            pass

        # TODO: name should be set earlier, as an opts?
        if opts:
            # TODO: encapsulate this logic, expand as needed
            # could also implement a check upfront to see if the option is valid
            # functions to configure
            for o in opts:
                try:
                    # TODO: the config logic of these four blocks needs to be checked
                    # > check constraint(**config)
                    # TODO: .endswith("_regularizer")?
                    if (
                        o == "kernel_regularizer"
                        or o == "bias_regularizer"
                        or o == "activity_regularizer"
                    ):
                        # TODO: I'm not sure why the regularizer needs to be called()
                        # but the activation and initializer don't?
                        reg = _configure_regularizer(opts[o])

                        functional_opts[o] = reg()
                    elif o == "activation":
                        functional_opts[o] = _configure_activation(opts[o])
                    elif o == "kernel_initializer" or o == "bias_initializer":
                        functional_opts[o] = _configure_initializer(opts[o])
                    elif o == "kernel_constraint" or o == "bias_constraint":
                        constraint = _configure_constraint(opts[o])
                        # print("here_________a")
                        # print(constraint)
                        # print(constraint.get_config())
                        # print("here_________b")
                        # sys.exit()
                        functional_opts[o] = constraint
                except ValueError as e:
                    raise ValueError(
                        f"error creating option {o} for layer {l_name}:\n > {e}"
                    )
                except TypeError as e:
                    raise TypeError(
                        f"error creating option {o} for layer {l_name}:\n > {e}"
                    )
            cur_layer = func(**functional_opts, name=l_name)
        else:
            cur_layer = func(name=l_name)

    return cur_layer


def build_hidden_block(model_cdict: dict, logger, g_logger) -> dict:

    logger.info("-> START building hidden block")
    HIDDEN_LAYERS = {}

    # build each layer based on the (ordered) yaml specification
    logger.debug(f"loop+start building layers: {model_cdict['layers'].keys()}")

    # NOTE: ordered_l_names is used to provide the input to a layer if one is not
    # specified.
    ordered_l_names = []
    for i, l_name in enumerate(model_cdict["layers"]):
        ordered_l_names.append(l_name)
        layer_info = model_cdict["layers"][str(l_name)]
        opts = layer_info["options"]
        ltype = layer_info["type"].lower()
        cur_layer = build_layer(ltype, opts, l_name, logger, g_logger)

        # elif ltype == "embedding":
        #     cur_layer = build_embedding_layer(opts, l_name, logger, g_logger)
        # elif ltype == "batch_normalization":
        #     cur_layer = build_batch_normalization_layer(opts, l_name, logger, g_logger)
        # elif ltype == "recurrent":
        #     cur_layer = build_recurrent_layer(opts, actfn, l_name, logger, g_logger)
        # else:
        #     raise NotImplementedError(f"layer type: {ltype} not implemented yet")

        # TODO this could probably be checked in the parsing logic
        # TODO: eventually, duplicate names could be included but a _n could
        # be appended. However, this is dangerous because then we would be assuming what
        # the user meant -- which isn't ideal
        if l_name in HIDDEN_LAYERS.keys():
            raise ValueError(
                f"layer {l_name} already exists in [{HIDDEN_LAYERS.keys()}] and duplicate names are not allowed. please change the name of {l_name}"
            )
        # HIDDEN_LAYERS[l_name] = cur_layer
        HIDDEN_LAYERS[l_name] = {}
        HIDDEN_LAYERS[l_name]["layer_fn"] = cur_layer

        # set layer input name
        if layer_info["input_str"]:
            HIDDEN_LAYERS[l_name]["input_str"] = layer_info["input_str"]
        elif i == 0:
            # TODO: this could likely be handled more elegantly. this ensures the
            # first layer uses the data input. The logic here will likely need to be
            # reconsidered. The issue is that we are 1) hard coding `'data_input'` and
            # 2) we are not ensuring the data_generator and input align. 3) we are no
            # longer allowed to use data_input as a layer name
            HIDDEN_LAYERS[l_name]["input_str"] = "data_input"
        else:
            # NOTE: if input not specified, assume sequential. This will need to be
            # documented.
            prev_name = ordered_l_names[i - 1]
            HIDDEN_LAYERS[l_name]["input_str"] = prev_name

    logger.info("[END] building hidden block")

    return HIDDEN_LAYERS