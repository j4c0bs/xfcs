#!/usr/bin/env python3

import argparse
from itertools import compress
import os
import time

from XFCS.FCSFile.FCSFile import FCSFile
from XFCS.utils.locator import locate_fcs_files
from XFCS.utils import metadata_csv
from XFCS.utils.metadata_stats import add_param_mean
from XFCS.version import VERSION

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
        '--kw-filter', '-k', type=argparse.FileType('r'), metavar='<user_kw.csv>',
        dest='kw_filter', help='Filter output with USER KeyWord preferences file.')

    kw_merge.add_argument(
        '--get-kw', '-g', action='store_true', dest='get_kw',
        help='Generate user keyword text file.')

    parser.add_argument(
        '--tidy', '-t', action='store_true',
        help='Outputs CSV in tidy (long) format.')

    parser.add_argument('-v', '--version', action='version', version=VERSION)

    return parser.parse_args()


# ------------------------------ KEYWORD PREFS ---------------------------------
def read_kw_prefs(kw_filter_file):
    """Read user selected keywords from text file.

    Arg:
        kw_filter_file: filepath to user kw text file.

    Returns:
        user_meta_keys: iterable of fcs Parameter keys.
    """

    user_meta_keys = None
    with open(kw_filter_file, 'r') as kw_file:
        user_meta_keys = [line.strip() for line in kw_file if line.strip() != '']
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
def load_metadata(paths, to_csv=True):
    """
        --> makes hashtable -> filepath : fcs file class instance
        meta_keys == all_keys w any new keys extended
        replaced -> meta_keys = ['FILEPATH'] with 'SRC_FILE'
    """

    fcs_objs = []
    meta_keys = ['SRC_DIR', 'SRC_FILE', 'CSV_CREATED']

    for filepath in paths:
        fcs = FCSFile()
        fcs.load(open(filepath, 'rb'))
        if to_csv:
            # fcs.set_param('SRC_FILE', os.path.abspath(src_file))
            src_dir, src_file = os.path.split(os.path.abspath(filepath))
            fcs.set_param('SRC_DIR', src_dir)
            fcs.set_param('SRC_FILE', src_file)
            fcs.set_param('CSV_CREATED', time.strftime('%m/%d/%y %H:%M:%S'))

        # TODO: make key check more efficient
        meta_keys.extend((mk for mk in fcs.param_keys if mk not in meta_keys))
        fcs_objs.append(fcs)

    return fcs_objs, meta_keys


# ------------------------------------------------------------------------------
def apply_keyword_filter(fcs_objs, kw_filter_file):
    """Gets user meta kw and applies stats if selected"""

    user_meta_keys = read_kw_prefs(kw_filter_file)
    valid_keys = add_param_mean(fcs_objs, user_meta_keys)
    return valid_keys


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

    # >>> for testing, disable writing csv files in place
    desc = '-t' if tidy else '-w'
    filename = fcs_name.split('.')[0]
    csv_fn = '{}_metadata{}.csv'.format(filename, desc)
    if fcs_dir:
        csv_fn = os.path.join(fcs_dir, csv_fn)

    return csv_fn


def batch_separate_metadata(fcs_objs, meta_keys, tidy):
    """Batch process all fcs to their own csv file.

    Args:
        fcs_objs: iterable of loaded FCSFile instances.
        meta_keys: iterable of fcs metadata Parameter keys to use.
        tidy: bool - enables tidy data format.

    Returns:
        csv_paths: iterable of filepaths to generated csv files.
    """

    src_keys = ('SRC_DIR', 'SRC_FILE', 'CSV_CREATED')
    csv_paths = []
    for fcs in fcs_objs:
        sep_keys = tuple(key for key in meta_keys if fcs.has_param(key) or key in src_keys)
        # csv_fn = fcs_to_csv_path(fcs.param('SRC_FILE'), fcs.param('SRC_DIR'), tidy=tidy)
        csv_fn = fcs_to_csv_path(fcs.param('SRC_FILE'), tidy=tidy)
        metadata_csv.write_file((fcs,), sep_keys, csv_fn, tidy)
        csv_paths.append(csv_fn)
    return csv_paths


# ------------------------------------------------------------------------------
def collect_filepaths(in_paths, recursive, limit=0):
    """Locate and limit fcs filepaths"""

    if in_paths:
        fcs_paths = [infile.name for infile in in_paths if infile.name.lower().endswith('.fcs')]
    else:
        fcs_paths = locate_fcs_files(recursive)

    if limit:
        # TODO: safe ctime -> or use $DATE in metadata
        fcs_paths.sort(key=lambda fn: os.path.getctime(fn))
        fcs_paths = fcs_paths[-limit:]

    return fcs_paths


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
    """Append new fcs file(s) metadata to existing fcs metadata csv file."""

    merge_keys, merge_data, is_tidy = metadata_csv.read_file(master_csv, meta_keys)

    if not all((merge_keys, merge_data)):
        print('>>> No metadata keys match / data located')
        return

    csv_fcs_objs = batch_load_fcs_from_csv(merge_keys, merge_data)

    # >>> check duplicate fcs metadata entries
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
    paths = collect_filepaths(args.input, args.recursive, args.limit)
    print('>>> fcs files located:', len(paths))
    if not paths:
        return

    to_csv = not args.get_kw
    fcs_objs, meta_keys = load_metadata(paths, to_csv)

    if args.get_kw:
        kw_prefs_filename = write_kw_prefs(meta_keys)
        print('>>> FCS Keyword file generated:', kw_prefs_filename)

    elif args.merge:
        master_csv = args.merge.name
        fn_out = master_csv if not args.output else args.output.name
        append_metadata(fcs_objs, meta_keys, master_csv, fn_out)

    else:
        if args.kw_filter:
            meta_keys = apply_keyword_filter(fcs_objs, args.kw_filter.name)

        if args.sepfiles:
            csv_paths = batch_separate_metadata(fcs_objs, meta_keys, args.tidy)
            print('>>> csv files written: {}'.format(len(csv_paths)))
        else:
            fn_out = '' if not args.output else args.output.name
            csv_out_path = merge_metadata(fcs_objs, meta_keys, args.tidy, fn_out)
            print('>>> csv file written to: {}'.format(csv_out_path))


# ------------------------------------------------------------------------------
