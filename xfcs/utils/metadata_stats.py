from collections import deque
from itertools import compress
import re
from statistics import mean

# ------------------------------- KW  STATS ------------------------------------

def prep_re_group(re_groupdict):
    """Extracts and prepares keyword match groups.

    Arg:
        re_groupdict: re.match.groupdict() instance.

    Returns:
        parameter keyword, historic mean range, $PxN channel name
    """

    param_key = re_groupdict.get('param')
    channel_name = re_groupdict.get('channel', '').strip('_').replace(' ','').upper()
    tmp_val = re_groupdict.get('val', '')
    if not tmp_val:
        mean_range = 10
    else:
        mean_range = int(tmp_val.strip('_'))

    return param_key, mean_range, channel_name


def config_spx_mean_keys(fcs_objs, spx_keys):
    """Configures keywords for $Px params.

    Arg:
        fcs_objs: iterable of fcs objects
        spx_keys: iterable of re.match instances

    Returns:
        spx_mean_keys: iterable of configured keywords needed to add mean values
    """

    spx_mean_keys = []

    for spx_key in spx_keys:
        param_key, mean_range, channel_name = prep_re_group(spx_key.groupdict())
        attr = ''.join(a for a in param_key[3:] if a.isalpha())
        new_data_key = '$Px{}_{}'.format(attr, channel_name)

        for fcs in fcs_objs:
            if fcs.has_param(new_data_key):
                data_key = new_data_key
            else:
                data_key = fcs.get_attr_by_channel_name(channel_name, attr)
                if data_key:
                    fcs.set_param(new_data_key, fcs.param(data_key))

        mean_key = '{}_MEAN_{}'.format(new_data_key, mean_range)
        force_key = new_data_key
        user_key = spx_key.string
        key_group = (data_key, force_key, mean_key, mean_range)
        spx_mean_keys.append((user_key, key_group))

    return spx_mean_keys


def config_param_mean_keys(par_keys):
    """Configures keywords for non-$Px params.

    Arg:
        par_keys: iterable of re.match instances

    Returns:
        param_mean_keys: iterable of configured keywords needed to add mean values
    """

    param_mean_keys = []
    for par_match in par_keys:
        data_key, mean_range, _ = prep_re_group(par_match.groupdict())
        mean_key = par_match.string
        force_key = data_key

        user_key = par_match.string
        key_group = (data_key, force_key, mean_key, mean_range)

        param_mean_keys.append((user_key, key_group))
    return param_mean_keys


def find_mean_keys(fcs_objs, user_meta_keys):
    """Locates any user requested mean keyword.
    Mean keyword format examples:
        $P8V_FL5LOG_MEAN_10, $PxV_FL5LOG_MEAN_10, $PxV_FL5LOG_MEAN
        $TOT_MEAN_10, $TOT_MEAN

    Args:
        fcs_objs: iterable of fcs objects
        user_meta_keys: all selected metadata keywords

    Returns:
        mean_keys: iterable of configured keywords needed to add mean values
    """

    spx_re = r'^(?P<param>\$P(x|\d+)\w)_(?P<channel>\w+)_MEAN(?P<val>_\d+)?$'
    spx_mean = re.compile(spx_re, re.IGNORECASE)
    par_mean = re.compile(r'^(?P<param>.+)_MEAN(?P<val>_\d+)?$')

    mean_keys, spx_keys, par_keys = [], [], []

    for kw in user_meta_keys:
        spx_match = spx_mean.match(kw)
        if spx_match:
            spx_keys.append(spx_match)
        else:
            par_match = par_mean.match(kw)
            if par_match:
                par_keys.append(par_match)

    if spx_keys:
        mean_keys.extend(config_spx_mean_keys(fcs_objs, spx_keys))
    if par_keys:
        mean_keys.extend(config_param_mean_keys(par_keys))
    return mean_keys


def add_param_mean(fcs_objs, user_meta_keys):
    """Calculates rolling mean for any user selected parameter keyword.
        Confirms parameter's have numeric values and exist within each fcs file.
        Adds new parameter keywords for any mean values relating to a $PX param.

    Args:
        fcs_objs: iterable of loaded FCSFile instances.
        user_meta_keys: iterable of param keys read from user_kw_prefs text file
            or keys found in master csv for appending new data.

    Returns:
        user_meta_keys: param keyword list filtered for any missing or malformed
            user keywords.
    """

    if not any('_MEAN' in key.upper() for key in user_meta_keys):
        return user_meta_keys

    mean_keys = find_mean_keys(fcs_objs, user_meta_keys)
    if not mean_keys:
        return user_meta_keys

    ignore_keys = []

    for user_key, key_group in mean_keys:
        data_key, force_key, mean_key, mean_range = key_group

        if not any(fcs.has_param(force_key) for fcs in fcs_objs):
            ignore_keys.extend((data_key, force_key, mean_key))
            continue

        elif not all(fcs.param_is_numeric(force_key) for fcs in fcs_objs):
            ignore_keys.extend((data_key, force_key, mean_key))
            continue

        channel_mean = []
        ch_queue = deque(maxlen=mean_range)
        spx_data = (fcs.numeric_param(force_key) for fcs in fcs_objs)

        # calculate all rolling mean values for parameter
        for channel_value in spx_data:
            ch_queue.append(channel_value)
            channel_mean.append(mean(ch_queue))

        # sets mean param, value for each fcs object
        for fcs, channel_value in zip(fcs_objs, channel_mean):
            fcs.set_param(mean_key, round(channel_value, 4))

        # force parameter keys included if only kw_MEAN in user kw file
        if force_key not in user_meta_keys:
            if user_key == mean_key:
                ix = user_meta_keys.index(mean_key)
                user_meta_keys.insert(ix, force_key)
            else:
                user_meta_keys.append(force_key)

        # replaces user $PnA_MEAN key with $PxA_MEAN
        if user_key != mean_key:
            user_meta_keys.append(mean_key)
            ignore_keys.append(user_key)

    if ignore_keys:
        drop_keys = (k not in ignore_keys for k in user_meta_keys)
        user_meta_keys = tuple(compress(user_meta_keys, drop_keys))

    return user_meta_keys


# ------------------------------------------------------------------------------
