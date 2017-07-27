#!/usr/bin/env python3

import argparse
from itertools import compress
import os
import sys
import time

from xfcs.FCSFile.FCSFile import FCSFile
from xfcs.utils import metadata_csv, metadata_time
from xfcs.utils.locator import locate_fcs_files
from xfcs.utils.metadata_stats import add_param_mean
from xfcs.version import VERSION

# ------------------------------------------------------------------------------
FORCED_SRC_KEYS = ('CSV_CREATED', 'SRC_DIR', 'SRC_FILE')

# ------------------------------------------------------------------------------
def parse_arguments():
    """Parse command line arguments."""

    parser = argparse.ArgumentParser(prog='xfcs', description='Parse FCS Metadata')

    csv_in = parser.add_argument_group('Input Options')
    csv_in.add_argument(
        '--input', '-i', nargs='+', type=argparse.FileType('rb'), metavar='<file.fcs>',
        help='Optional select input file(s) instead of default directory search.')

    csv_in.add_argument(
        '--recursive', '-r', action='store_true', dest='recursive',
        help='Enable recursive search of current directory.')

    csv_in.add_argument(
        '--limit', '-l', type=int, default=0, metavar='n',
        help='Number of most recent files to parse.')

    csvout = parser.add_argument_group('Output Option - select 1')
    outgrp = csvout.add_mutually_exclusive_group()

    outgrp.add_argument(
        '--sep-files', '-s', action='store_true', dest='sepfiles',
        help='Each input FCS file generates one csv file.')

    outgrp.add_argument(
        '--output', '-o', type=argparse.FileType('w'), metavar='<file.csv>',
        help='Output .csv filepath for merged metadata file.')

    procopt = parser.add_argument_group('Metadata Option - select 1')
    kw_merge = procopt.add_mutually_exclusive_group()

    kw_merge.add_argument(
        '--append-to', '-a', type=argparse.FileType('r'), metavar='<metadata.csv>',
        dest='merge', help='Append fcs metadata to existing fcs metadata csv file.')

    kw_merge.add_argument(
        '--kw-filter', '-k', type=argparse.FileType('r'), metavar='<user_kw.txt>',
        dest='kw_filter', help='Filter output with USER KeyWord preferences file.')

    kw_merge.add_argument(
        '--get-kw', '-g', action='store_true', dest='get_kw',
        help='Generate user keyword text file.')

    parser.add_argument(
        '--thirdnormal', '-t', action='store_true', dest='tidy',
        help='Outputs CSV in third normal form (long).')

    parser.add_argument('-v', '--version', action='version', version=VERSION)

    return parser.parse_args()


# ------------------------------ KEYWORD PREFS ---------------------------------
def read_kw_prefs(kw_filter_file):
    """Read user selected keywords from text file and insert forced src keys
        if not included by user.

    Arg:
        kw_filter_file: filepath to user kw text file.

    Returns:
        user_meta_keys: iterable of fcs Parameter keys.
    """

    user_meta_keys = None
    with open(kw_filter_file, 'r') as kw_file:
        user_meta_keys = [line.strip() for line in kw_file if line.strip() != '']

    for key in reversed(FORCED_SRC_KEYS):
        if key not in user_meta_keys:
            user_meta_keys.insert(0, key)

    return user_meta_keys


def write_kw_prefs(meta_keys):
    """Write all located fcs Parameter keys to text file

    Arg:
        meta_keys: iterable of fcs metadata Parameter keys in order relative to
            location in fcs file text section.

    Returns:
        kw_prefs_filename: name of generated text file
    """

    kw_prefs_filename = 'FCS_USER_KW.txt'
    with open(kw_prefs_filename, 'w') as kw_file:
        for keyword in meta_keys:
            kw_file.write('{}\n'.format(keyword))

    return kw_prefs_filename


# ------------------------------------------------------------------------------
def load_metadata(paths):
    """
        --> makes hashtable -> filepath : fcs file class instance
        meta_keys == all_keys w any new keys extended
        replaced -> meta_keys = ['FILEPATH'] with 'SRC_FILE'

    Arg:
        paths: iterable of fcs filepaths

    Returns:
        fcs_objs:
        meta_keys:
    """

    fcs_objs = []
    meta_keys = []
    meta_keys.extend(FORCED_SRC_KEYS)

    for filepath in paths:
        fcs = FCSFile()
        fcs.load(filepath)
        fcs.set_param('CSV_CREATED', time.strftime('%m/%d/%y %H:%M:%S'))
        fcs.set_param('SRC_DIR', fcs.parentdir)
        fcs.set_param('SRC_FILE', fcs.name)

        meta_keys.extend((mk for mk in fcs.param_keys if mk not in meta_keys))
        fcs_objs.append(fcs)
        fcs.close()

    return fcs_objs, meta_keys


# ------------------------------------------------------------------------------
def merge_metadata(fcs_objs, meta_keys, tidy, fn_out=''):
    """All fcs metadata written to one csv file.

    Args:
        fcs_objs: iterable of loaded FCSFile instances.
        meta_keys: iterable of fcs metadata Parameter keys to use.
        tidy: bool - enables tidy data format.
        fn_out: optional filepath/name for csv file.

    Returns:
        csv_fn: filename of generated csv.
    """

    if fn_out:
        csv_fn = fn_out
    else:
        desc = '-t' if tidy else '-w'
        curdir_name = os.path.basename(os.getcwd())
        csv_fn = '{}_FCS_metadata{}.csv'.format(curdir_name, desc)

    metadata_csv.write_file(fcs_objs, meta_keys, csv_fn, tidy)
    return csv_fn


def fcs_to_csv_path(fcs_name, fcs_dir='', tidy=False):
    """Convert fcs filename to csv_metadata filename."""

    desc = '-t' if tidy else '-w'
    filename = fcs_name.split('.')[0]
    csv_fn = '{}_metadata{}.csv'.format(filename, desc)
    if fcs_dir:
        csv_fn = os.path.join(fcs_dir, csv_fn)

    return csv_fn


def write_obj_metadata(fcs):
    meta_keys = list(FORCED_SRC_KEYS)
    meta_keys.extend(fcs.param_keys)
    csv_fn = fcs_to_csv_path(fcs.name, fcs.parentdir)
    fcs.set_param('CSV_CREATED', time.strftime('%m/%d/%y %H:%M:%S'))
    fcs.set_param('SRC_DIR', fcs.parentdir)
    fcs.set_param('SRC_FILE', fcs.name)
    metadata_csv.write_file((fcs,), meta_keys, csv_fn, tidy=False)


def batch_separate_metadata(fcs_objs, meta_keys, tidy):
    """Batch process all fcs to their own, separate csv file.

    Args:
        fcs_objs: iterable of loaded FCSFile instances.
        meta_keys: iterable of fcs metadata Parameter keys to use.
        tidy: bool - enables tidy data format.

    Returns:
        csv_paths: iterable of filepaths to generated csv files.
    """

    csv_paths = []
    for fcs in fcs_objs:
        sep_keys = tuple(key for key in meta_keys if fcs.has_param(key))
        csv_fn = fcs_to_csv_path(fcs.name, fcs.parentdir, tidy=tidy)
        metadata_csv.write_file((fcs,), sep_keys, csv_fn, tidy)
        csv_paths.append(csv_fn)
    return csv_paths


# ------------------------------------------------------------------------------
def get_fcs_paths(in_paths, recursive, limit=0):
    """Locate and sort / limit fcs filepaths if not using --input arg.
        Dir search, sorting and limit is disabled if in_paths is not empty.
        In dir search, files are sorted by filename. If limit is enabled, an
        attempt to sort via os.path.getctime is made. If this fails, further
        sorting is attempted within main() based on sort_confirmed value.

    Args:
        in_paths: iterable of fcs paths from args.input, disables dir search.
        recursive: bool - enables recursive dir search.
        limit: int - concatenates located files if using dir search.

    Returns:
        fcs_paths: iterable of fcs filepaths.
        sort_confirmed: bool - confirms attempt to sort paths by ctime.
    """

    if in_paths:
        fcs_paths = [infile.name for infile in in_paths if infile.name.lower().endswith('.fcs')]
    else:
        fcs_paths = locate_fcs_files(recursive)

    sort_confirmed = True

    if limit and not in_paths:
        by_ctime = metadata_time.sort_by_ctime(fcs_paths)
        if by_ctime:
            fcs_paths = by_ctime[-limit:]
        else:
            sort_confirmed = False

    return fcs_paths, sort_confirmed


# ------------------------------------------------------------------------------
def batch_load_fcs_from_csv(merge_keys, merge_data):
    """Init FCSFile instances using extracted metadata from csv file."""

    merge_objs = []
    for param_vals in merge_data:
        fcs = FCSFile()
        fcs.load_from_csv(merge_keys, param_vals)
        merge_objs.append(fcs)
    return merge_objs


def append_metadata(fcs_objs, meta_keys, master_csv, fn_out):
    """Append new fcs file(s) metadata to existing fcs metadata csv file.
        USER_KW_PREFS is bypassed and keyword set from master csv acts as
        keyword filter.

    """

    merge_keys, merge_data, is_tidy = metadata_csv.read_file(master_csv, meta_keys)

    if not all((merge_keys, merge_data)):
        print('>>> No metadata keys match / data located')
        return

    csv_fcs_objs = batch_load_fcs_from_csv(merge_keys, merge_data)

    # check duplicate fcs metadata entries
    comparison_keys = [key for key in merge_keys if key in meta_keys]

    csv_fcs_hashes = set(fcs.meta_hash(comparison_keys) for fcs in csv_fcs_objs)
    incoming_hashes = [fcs.meta_hash(comparison_keys) for fcs in fcs_objs]
    hash_filter = [md_hash not in csv_fcs_hashes for md_hash in incoming_hashes]

    all_fcs_objs = []
    all_fcs_objs.extend(csv_fcs_objs)

    if not all(hash_filter):
        unique_fcs = tuple(compress(fcs_objs, hash_filter))
        if not unique_fcs:
            print('>>> No unique fcs files to append to master csv')
            return
        else:
            all_fcs_objs.extend(unique_fcs)
    else:
        all_fcs_objs.extend(fcs_objs)

    merge_keys = add_param_mean(all_fcs_objs, merge_keys)
    csv_out_path = merge_metadata(all_fcs_objs, merge_keys, is_tidy, fn_out)
    print('>>> fcs metadata appended to: {}'.format(csv_out_path))


# ------------------------------------------------------------------------------
def main():
    """Main control for CLI metadata extraction.

        fcs_objs: iterable of metadata dicts
        meta_keys: all_keys in order + any new (calculated) keys at end
    """

    args = parse_arguments()
    paths, sort_confirmed = get_fcs_paths(args.input, args.recursive, args.limit)
    print('>>> fcs files located:', len(paths))
    if not paths:
        sys.exit(0)

    fcs_objs, meta_keys = load_metadata(paths)

    # TODO: add arg to force param time sort?
    if not sort_confirmed:
        sorted_fcs = metadata_time.sort_by_time_params(fcs_objs)
        if not sorted_fcs:
            print('>>> Unable to access any time related metadata for fcs files.')
            print('>>> Disable --limit option in command and manually list --input files.')
            sys.exit(0)

        fcs_objs = sorted_fcs[-args.limit:]

    if args.get_kw:
        kw_prefs_filename = write_kw_prefs(meta_keys)
        print('>>> FCS Keyword file generated:', kw_prefs_filename)

    elif args.merge:
        master_csv = args.merge.name
        fn_out = master_csv if not args.output else args.output.name
        append_metadata(fcs_objs, meta_keys, master_csv, fn_out)

    else:
        if args.kw_filter:
            meta_keys = read_kw_prefs(args.kw_filter.name)
            check_user_mean_keys = any('_MEAN' in key for key in meta_keys)
        else:
            check_user_mean_keys = False

        if args.sepfiles:
            csv_paths = batch_separate_metadata(fcs_objs, meta_keys, args.tidy)
            print('\n>>> csv files written: {}\n'.format(len(csv_paths)))
        else:
            if check_user_mean_keys:
                meta_keys = add_param_mean(fcs_objs, meta_keys)

            fn_out = '' if not args.output else args.output.name
            csv_out_path = merge_metadata(fcs_objs, meta_keys, args.tidy, fn_out)
            print('\n>>> csv file written to: {}\n'.format(csv_out_path))


# ------------------------------------------------------------------------------
