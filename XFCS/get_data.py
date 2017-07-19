
import argparse
from collections import namedtuple
# from itertools import compress
import os
import sys
import time

from XFCS.FCSFile.FCSFile import FCSFile
from XFCS.get_metadata import write_obj_metadata
from XFCS.utils.locator import locate_fcs_files
from XFCS.version import VERSION
# ------------------------------------------------------------------------------

def parse_arguments():
    """Parse command line arguments."""

    parser = argparse.ArgumentParser(prog='xfcsdata', description='Extract FCS Data')

    fcs_in = parser.add_argument_group('Input Options')
    fcs_in.add_argument(
        '--input', '-i', nargs='+', type=argparse.FileType('rb'), metavar='<file.fcs>',
        help='Optional select input file(s) instead of default directory search.')

    fcs_in.add_argument(
        '--recursive', '-r', action='store_true', dest='recursive',
        help='Enable recursive search of current directory.')

    dsval = parser.add_argument_group('Data Set Options')

    dsval.add_argument('--raw', '-w', action='store_true', help='Raw data values.')
    dsval.add_argument('--channel', '-c', action='store_true', help='Channel data values.')
    dsval.add_argument('--scale', '-s', action='store_true', dest='scale', help='Log scale data values.')
    dsval.add_argument('--xcxs', '-x', action='store_true', help='Log scale values and any non-log channel values.')
    dsval.add_argument('--fl-comp', '-f', action='store_true', dest='fl_comp', help='Fluorescence compensated data values.')
    dsval.add_argument('--scale-fl-comp', '-p', action='store_true', dest='scale_fl_comp', help='Log scaled, fluorescence compensated data values.')

    fcs_out = parser.add_argument_group('Output Options')
    fcs_out.add_argument('--norm-count', '-n', dest='norm_count', action='store_true', help='Normalize event count to start at 1, or forces inclusion in data set if any $PnN=<event count> not located.')
    fcs_out.add_argument('--hdf5', action='store_true', help='Use HDF5 filetype for data instead of csv.')
    fcs_out.add_argument('--metadata', '-m', action='store_true', help='Generate metadata csv file for each fcs file.')
    parser.add_argument('-v', '--version', action='version', version=VERSION)
    return parser.parse_args()


# ------------------------------------------------------------------------------

def store_hdf5_data(data_set, data_desc, filepath):
    # >>> fix names
    data_name = os.path.basename(filepath.rsplit('.', 1)[0]).replace(' ', '_')
    data_path = filepath.rsplit('.', 1)[0] + '_{}.h5'.format(data_desc)
    data_set.to_hdf(data_path, data_name, mode='w', complib='zlib', complevel=9)


def store_csv_data(data_set, data_desc, filepath):
    data_path = filepath.rsplit('.', 1)[0] + '_{}.csv'.format(data_desc)
    data_set.to_csv(data_path, index=False)


def batch_export_data(fcs_paths, get_data, metadata, norm_count, hdf):

    if hdf:
        store_data = store_hdf5_data
    else:
        store_data = store_csv_data

    get_options = ('raw', 'channel', 'scale', 'xcxs', 'fl_comp', 'scale_fl_comp')
    data_attrs = ('raw', 'channel', 'scale', 'channel_scale', 'compensated', 'scale_compensated')

    user_select = []

    for user_option, data_attr in zip(get_options, data_attrs):
        if getattr(get_data, user_option):
            user_select.append((user_option, data_attr))


    for path in fcs_paths:
        fcs = FCSFile()
        fcs.load(path)
        fcs.load_data(norm_count)

        for user_option, data_attr in user_select:
            data_set = getattr(fcs.data, data_attr)
            if data_set is not None:
                store_data(data_set, user_option, path)
            else:
                print('>>> fcs data set <{}> is unavailable.'.format(user_option))

        if metadata:
            write_obj_metadata(fcs)

# ------------------------------------------------------------------------------
# TODO: implement --metadata
# ------------------------------------------------------------------------------
def main():
    args = parse_arguments()
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

    batch_export_data(fcs_paths, get_data(*set_choices), args.metadata, args.norm_count, args.hdf5)

    end = time.perf_counter() - start
    print('{:.4f} sec'.format(end))

    print()


# ------------------------------------------------------------------------------
# if get_data.raw:
#     data_set = fcs.data.raw
#     store_data(data_set, 'raw', path)
#
# if get_data.channel:
#     data_set = fcs.data.channel
#     store_data(data_set, 'channel', path)
#
# if get_data.scale:
#     data_set = fcs.data.scale
#     if data_set is not None:
#         print('>>> No parameters have have log or gain scale to apply.')
#         store_data(data_set, 'scale', path)
#
# if get_data.xcxs:
#     data_set = fcs.data.channel_scale
#     store_data(data_set, 'xcxs', path)
#
# if get_data.fl_comp:
#     data_set = fcs.data.compensated
#     if data_set is not None:
#         store_data(data_set, 'fl_comp', path)
#
# if get_data.scale_fl_comp:
#     data_set = fcs.data.scale_compensated
#     if data_set is not None:
#         store_data(data_set, 'scale_fl_comp', path)
# ------------------------------------------------------------------------------
