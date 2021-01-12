"""
Object utils module.

Used in the old automod module which is now abandoned.
"""

import inspect
import time
from datetime import timedelta
from distutils.util import strtobool
from functools import wraps
from typing import Callable, Tuple, Union

import typeguard
from loguru import logger


def get_id(type_identifier: int, counter: int) -> int:
    """
    Generates ID of an object based on the ID counter.

    ID Format: TTTTTTTTinnnnC, where TTTTTTTT is the last 8 digits of
    the UNIX timestamp (seconds accuracy), i is the type identifier
    digit, n is a 4-digit counter (which should be sufficient to avoid
    clashes due to it being larger than the default cache size) and C is
    the check digit, which is just the product of the identifier digit,
    the timestamp, and the counter mod 10.

    The IDs generated by this are at least 4 digits shorter than the
    average Discord Snowflake, but there is a possibility for it to
    generate similar IDs every 3 years or so (hopefully no cache that
    has been configured for this bot is actually that long). It is
    possible to just use Discord's snowflakes instead of this but the
    purpose is to have distinct IDs.

    :param type_identifier: Identifier digit, to be prepended to the ID
    :param counter: Counter from the metaclass
    :return: ID generated from counter
    """
    identifier = type_identifier
    date = int(time.time()) % 100000000
    count = counter + 1
    check = (identifier * date * count) % 10

    # Zeros:       innnnC                 nnnnC            C
    return date * 1000000 + identifier * 100000 + count * 10 + check


def match_param(
        original_param: Union[str, int, float, bool, timedelta],
        new_param: str
) -> Tuple[
    Union[str, int, float, bool],
    Union[str, int, float, bool, timedelta]
]:
    """
    Casts string input into corresponding parameter type.

    :param original_param: Original parameter
    :param new_param: New parameter in string
    :return: Tuple of the new parameter casted to a YAML-friendly type
        and the new parameter casted to the same type as the original
    :raises ValueError: If parameter type is invalid or input parameter
        cannot be casted
    """
    if isinstance(original_param, str):
        return new_param, new_param
    if isinstance(original_param, bool):
        bool_param = bool(strtobool(new_param))  # Bools are also ints!
        return bool_param, bool_param
    if isinstance(original_param, int):
        int_param = int(new_param)
        return int_param, int_param
    if isinstance(original_param, float):
        float_param = float(new_param)
        return float_param, float_param
    if isinstance(original_param, timedelta):
        int_param = int(new_param)
        return int_param, timedelta(int_param)  # Time in seconds

    raise ValueError


class EnforceParamError(Exception):
    """Exception raised when param types don't match when enforced"""


def enforce_param_types(function: Callable) -> Callable:
    """
    Enforces parameter types based on type hints.

    :param function: Function to enforce input parameter types for
    :return: Wrapped function
    """

    @wraps(function)
    def wrapper(*args, **kwargs):
        logger.trace("Enforcing parameters for function {}", function.__name__)
        try:
            func_sig = inspect.signature(function)
            pos_params = [
                (p_name, p_type.annotation)
                for p_name, p_type in func_sig.parameters.items()
                if p_type.kind in {
                    inspect.Parameter.POSITIONAL_ONLY,
                    inspect.Parameter.POSITIONAL_OR_KEYWORD
                }
            ]
            logger.trace("Found positional parameters: {}", pos_params)

            keyword_params = {
                p_name: p_type.annotation
                for p_name, p_type in func_sig.parameters.items()
                if p_type.kind in {
                    inspect.Parameter.KEYWORD_ONLY,
                    inspect.Parameter.POSITIONAL_OR_KEYWORD
                }
            }
            logger.trace("Found keyword parameters: {}", keyword_params)

            # We check from index = 1 to skip self
            for index in range(1, min(len(args), len(pos_params))):
                logger.trace("Typeguard checking positional index: {}", index)
                typeguard.check_type(
                    pos_params[index][0],
                    args[index],
                    pos_params[index][1]
                )

            for k_name, k_value in kwargs.items():
                logger.trace(
                    "Typeguard checking keyword param: "
                    "{}: {} (Type expected: {})",
                    k_name,
                    k_value,
                    keyword_params[k_name]
                )
                typeguard.check_type(k_name, k_value, keyword_params[k_name])

            function(*args, **kwargs)

        except (TypeError, KeyError) as e:
            raise EnforceParamError(str(e)) from e

    return wrapper
