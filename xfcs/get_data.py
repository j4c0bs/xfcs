
from collections import namedtuple
import os
import sys
import time

from xfcs.FCSFile.FCSFile import FCSFile
from xfcs.get_metadata import write_obj_metadata
from xfcs.utils.locator import locate_fcs_files
from xfcs.version import VERSION
# ------------------------------------------------------------------------------
def store_hdf5_data(data_set, data_desc, filepath):
    # >>> fix names
    data_name = os.path.basename(filepath.rsplit('.', 1)[0]).replace(' ', '_')
    data_path = filepath.rsplit('.', 1)[0] + '_{}.h5'.format(data_desc)
    data_set.to_hdf(data_path, data_name, mode='w', complib='zlib', complevel=9)


def store_csv_data(data_set, data_desc, filepath):
    data_path = filepath.rsplit('.', 1)[0] + '_{}.csv'.format(data_desc)
    data_set.to_csv(data_path, index=False)


def batch_export_data(fcs_paths, data_choices, metadata, norm_count, norm_time, hdf):

    if hdf:
        store_data = store_hdf5_data
    else:
        store_data = store_csv_data

    get_options = ('raw', 'channel', 'scale', 'xcxs', 'fl_comp', 'scale_fl_comp')
    data_attrs = ('raw', 'channel', 'scale', 'channel_scale', 'compensated', 'scale_compensated')

    user_select = []

    for user_option, data_attr in zip(get_options, data_attrs):
        if getattr(data_choices, user_option):
            user_select.append((user_option, data_attr))

    for path in fcs_paths:
        fcs = FCSFile()
        fcs.load(path)
        fcs.load_data(norm_count, norm_time)
        write_count = 0

        for user_option, data_attr in user_select:
            data_pkg = getattr(fcs.data, data_attr)
            data_names, data_set = data_pkg
            if data_pkg and data_names:
                store_data(data_set, user_option, path)
                write_count += 1
            else:
                print('>>> fcs data set <{}> is unavailable.'.format(user_option))

        print('>>> Data sets extracted to file:', write_count)

        if metadata:
            write_obj_metadata(fcs)
            print('>>> Metadata generated for:', fcs.name)

# ------------------------------------------------------------------------------
def main(args):
    if args.input:
        fcs_paths = [infile.name for infile in args.input if infile.name.lower().endswith('.fcs')]
    else:
        fcs_paths = locate_fcs_files(args.recursive)

    if not fcs_paths:
        print('No fcs files located')
        sys.exit(0)

    set_names = ('raw', 'channel', 'scale', 'xcxs', 'fl_comp', 'scale_fl_comp')
    set_choices = tuple(getattr(args, name) for name in set_names)
    get_data = namedtuple('GetData', set_names)

    start = time.perf_counter()

    data_choices = get_data(*set_choices)
    output_options = ('metadata', 'norm_count', 'norm_time', 'hdf5')
    output = (getattr(args, name) for name in output_options)
    batch_export_data(fcs_paths, data_choices, *output)

    end = time.perf_counter() - start
    n_files = len(fcs_paths)
    x_ave = end / n_files
    txt = '\nfcs files: {}, ave/total: {:.3f}/{:.3f} sec'.format(n_files, x_ave, end)
    print(txt)
    print()


# ------------------------------------------------------------------------------
