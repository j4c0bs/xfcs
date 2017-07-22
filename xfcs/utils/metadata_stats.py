from collections import deque
from itertools import compress
import re
from statistics import mean

# ------------------------------- $Px STATS ------------------------------------
def find_spx_mean_params(user_meta_keys):
    """Finds any user specified parameter keywords to include a rolling mean value.
        Example keywords: $P10V_MEAN, $P10V_MEAN_5, $TOT_MEAN

    Arg:
        user_meta_keys: iterable of param keys read from user_kw_prefs text file.

    Returns:
        param_key_ranges: iterable of tuples containing -
        parameter key, parameter_MEAN key, historic range int for rolling mean.
    """

    user_mean_key = re.compile(r'^(.+)_MEAN(_\d+)?$')

    param_key_ranges = []
    for param_mean_key in user_meta_keys:
        kw_match = user_mean_key.match(param_mean_key)

        if kw_match:
            param_key, mean_range = kw_match.groups()
            if mean_range:
                mean_range = int(mean_range.strip('_'))

            if not mean_range:
                mean_range = 10

            param_key_ranges.append((param_key, param_mean_key, mean_range))

    return param_key_ranges


def add_param_mean(fcs_objs, user_meta_keys):
    """Calculates rolling mean for any user selected parameter keyword.
        Confirms parameter's have numeric values and exist within each fcs file.

    Args:
        fcs_objs: iterable of loaded FCSFile instances.
        user_meta_keys: iterable of param keys read from user_kw_prefs text file.

    Returns:
        user_meta_keys: param keyword list filtered for any missing or malformed
            user keywords.
    """

    param_key_ranges = find_spx_mean_params(user_meta_keys)
    if not param_key_ranges:
        return user_meta_keys

    missing_spx_keys = []
    volt_keys = []

    for param_key, param_mean_key, mean_range in param_key_ranges:
        if not any(fcs.has_param(param_key) for fcs in fcs_objs):
            missing_spx_keys.extend((param_key, param_mean_key))
            continue
        elif not all(fcs.param_is_numeric(param_key) for fcs in fcs_objs):
            missing_spx_keys.append(param_mean_key)
            continue

        volt_keys.append((param_key, param_mean_key))

        volt_mean = []
        v_queue = deque(maxlen=mean_range)
        spx_data = (x.numeric_param(param_key) for x in fcs_objs)

        for volt in spx_data:
            v_queue.append(volt)
            volt_mean.append(mean(v_queue))

        for x, volt in zip(fcs_objs, volt_mean):
            x.set_param(param_mean_key, round(volt, 2))

    # force parameter keys included if only $Px_MEAN in user kw file
    for (param_key, param_mean_key) in volt_keys:
        if param_key not in user_meta_keys:
            ix = user_meta_keys.index(param_mean_key)
            user_meta_keys.insert(ix, param_key)

    if missing_spx_keys:
        drop_keys = (k not in missing_spx_keys for k in user_meta_keys)
        user_meta_keys = tuple(compress(user_meta_keys, drop_keys))

    return user_meta_keys


# ------------------------------------------------------------------------------
