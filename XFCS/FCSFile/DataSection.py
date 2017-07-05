#!/usr/bin/env python3

import os
import sys

import numpy as np
import pandas as pd

from .Parameter import Parameter
# ------------------------------------------------------------------------------
def x_endian(s):
    if s == '1,2,3,4':
        return 'little'
    elif s == '4,3,2,1':
        return 'big'
    else:
        raise ValueError

# ------------------------------------------------------------------------------
class DataSection(object):
    def __init__(self, text, data, file_name, keep_raw=False):
        self.text = text
        self.data = data
        self.file_name = file_name
        self.keep_raw = keep_raw
        self.load_metadata(text)
        self.data_name = None
        self.ver_id = None
        self.parameters = []
        self.raw_data = None
        self.bxn = None
        self.SPx_attr_log = {}
        self.xc_df = None

        self.add_parameters()
        self.check_fcs_file_conformity()
        self.extract_data()
        self.scale_data()

    def load_metadata(self, text):
        self.metadata = text

        # self.sBEGINDATA = text['$BEGINDATA']
        # self.sENDDATA = text['$ENDDATA']

        self.sDATATYPE = text['$DATATYPE']
        self.sMODE = text['$MODE']
        self.sBYTEORDER = x_endian(text['$BYTEORD'])
        self.sPAR = int(text['$PAR'])
        self.sTOT = int(text['$TOT'])
        self.sTIMESTEP = float(text['$TIMESTEP'])

        # >>> only for ev log
        self.sSMNO = text.get('$SMNO', None)
        self.sID = text.get('IC$WellID', None)
        self.sTR = text.get('$TR', None)

        self.flc_param_numbers = []
        if text.get('$SPILLOVER', None):
            self.load_spillover_matrix()

    # ---------------------------- DATA PACKAGE --------------------------------
    def get_data_package(self):
        return self.file_name, self.xc_df, self.metadata, self.SPx_attr_log

    # ------------------------ LOAD AXIS PARAMETERS ----------------------------
    def get_any_SPxX(self, A, verify_uniform=True):
        """Retrieves list of specific $Parameter attribute designated by arg A
           Performs optional check (kwarg - bool) to confirm all Parameter's attr are identical
           Returns: list of requested attribute for all $Parameters
        """

        # turn into dict w key=N, subkey=A

        all_xA = []
        for n in range(1,self.sPAR+1):
            SPx = '$P' + str(n) + A
            all_xA.append(self.text[SPx])

        if verify_uniform:
            if len(set(all_xA)) != 1:
                raise ValueError
            else:
                SPxA = all_xA[0]
        else:
            SPxA = all_xA

        return SPxA

    def add_parameters(self):
        """inits all Parameters instances
           Param attr args: (number, name, short_name, bits, scale, vrange)
           Collects any Parameters that are in $SPILLOVER matrix and instantiates Parameter class
        """

        self.param_name_lookup = {}
        # >>> flc_params[$PnX] = Parameter($PnX attr + FLC to name / short_name)
        self.flc_params = {}

        for n in range(1,self.sPAR+1):
            param_num = '$P' + str(n)
            attr_sfx = ['N','S','B','E','R']
            attr = [n]
            for attr_x in attr_sfx:
                attr.append(self.text[param_num+attr_x])

            axis_param = Parameter(*attr)
            self.parameters.append(axis_param)
            self.param_name_lookup[n] = axis_param.name

            if n in self.flc_param_numbers:
                flc_attr = attr[:]
                flc_attr[1] += ' FLC'
                flc_attr[2] += 'FLC'
                self.flc_params[n] = Parameter(*flc_attr)

        for param in self.parameters:
            # if param.short_name.lower() in ['time lsw', 'time msw']:
            #     continue
            param.generate_attr_log()
            self.SPx_attr_log[param.name] = param.attr_log

            if param.short_name.lower() in ['time', 'time msw']:
                time_attr = {}
                time_attr.update(param.attr_log)
                time_attr['short_name'] = 'time'
                self.SPx_attr_log['EVENT_TIME'] = time_attr

    # ---------------------- FCS FILE STANDARDS CHECK --------------------------
    def verify_format(self):

        SPxB = int(self.get_any_SPxX('B'))
        if SPxB % 8 != 0:
            print('DATA BYTE READ LENGTH NOT RECOGNIZED')
            return False
        else:
            self.bxn = SPxB

        if self.sMODE != 'L':
            print('FCS MODE NOT SUPPORTED - LIST MODE ONLY')
            return False
        elif self.sDATATYPE != 'I':
            print('FCS DATA TYPE NOT SUPPORTED')
            return False
        elif len(self.data) != (self.sPAR * self.sTOT * (self.bxn // 8)):
            print('UNABLE TO READ FCS DATA SECTION')
            return False

        return True

    def check_fcs_file_conformity(self):
        if not self.verify_format():
            print('FCS FILE DOES NOT CONFORM TO STANDARDS')
            print('ABORTING DATA EXTRACTION')
            sys.exit(0)

    # --------------------- DATA EXTRACT AND TRANSFORM -------------------------
    def extract_data(self):
        """ Parses Data Section and loads raw data into DataFrame
            Hex byte pairs separated into single list then split into $P dict key groups
        """

        SPxB = self.bxn // 8
        hex_bytes = [int.from_bytes(self.data[ix*SPxB:ix*SPxB+SPxB], self.sBYTEORDER)
                     for ix in range(len(self.data)//SPxB)]

        self.raw_data = {param.name: None for param in self.parameters}

        for ix in range(self.sPAR):
            key = self.parameters[ix].name
            xc = [hex_bytes[ix + self.sPAR * jx] for jx in range(self.sTOT)]
            self.raw_data[key] = xc

        self.xc_df = pd.DataFrame(self.raw_data,
                     columns = [param.name for param in self.parameters])

        self.generate_data_name()


    def scale_time(self, time_msw, time_lsw):
        """ Transforms time parameter using time lsw, msw
            Creates new data entry EVENT_TIME
        """

        def time_encode(msw, lsw):
            return ((msw << self.bxn) | lsw)

        vtime = np.vectorize(time_encode)
        self.xc_df['TIME_2xBits'] = vtime(self.xc_df[time_msw], self.xc_df[time_lsw])
        self.xc_df['DELTA'] = self.xc_df['TIME_2xBits'] - self.xc_df['TIME_2xBits'].ix[0]
        self.xc_df['EVENT_TIME'] = self.xc_df['DELTA'] * self.sTIMESTEP

        del self.xc_df['DELTA']
        del self.xc_df['TIME_2xBits']

        if not self.keep_raw:
            del self.xc_df[time_msw]
            del self.xc_df[time_lsw]

        self.event_time_maxrange = round(self.xc_df['EVENT_TIME'].max(), 6)
        self.SPx_attr_log['EVENT_TIME']['maxrange'] = np.ceil(self.event_time_maxrange)


    def scale_event_count(self):
        # TODO: --> add func to check for count roll over
        if self.keep_raw:
            self.xc_df['Cumulative Event Count'] = self.xc_df['Event Count']
            self.xc_df['Event Count'] =  self.xc_df.index + 1
        else:
            self.xc_df['Event Count'] =  self.xc_df.index + 1


    def load_spillover_matrix(self):
        spill = self.text['$SPILLOVER'].split(',')
        number_channels = int(spill[0])
        self.flc_param_numbers = [int(n) for n in spill[1:number_channels + 1]]
        comp_vals = [float(n) for n in spill[number_channels + 1:]]

        spill_matrix = np.array(comp_vals).reshape(number_channels, number_channels)
        diagonals = np.unique(spill_matrix[np.diag_indices(number_channels, number_channels)])

        if diagonals.size != 1:
            print('Aborting fluorescence compensation')
            return False

        spill_matrix = spill_matrix / diagonals.item(0)
        self.compensation_matrix = np.linalg.inv(spill_matrix)

        print('='*80)
        print(self.file_name)
        print('='*80)
        print('spill_matrix')
        print(spill_matrix)
        print('comp_matrix')
        print(self.compensation_matrix)


    def fluorescence_compensation(self):
        # >>>>>>> V2 w matrix init in advance >>>>>>> >>>>>>> >>>>>>> >>>>>>>
        print('_'*80)
        print('FLC NUMBERS', self.flc_param_numbers)

        for ix, pn in enumerate(self.flc_param_numbers):
            cvals = self.compensation_matrix[:,ix].sum()
            channel_name = self.param_name_lookup[pn]
            compensated_parameter = self.flc_params[pn]

            channel_compensated = compensated_parameter.name

            self.xc_df[channel_compensated] = self.xc_df[channel_name] * cvals

            self.SPx_attr_log[channel_compensated] = {}
            self.SPx_attr_log[channel_compensated].update(self.SPx_attr_log[channel_name])

            self.parameters.append(compensated_parameter)


    def scale_data(self):
        time_msw = ''
        time_lsw = ''
        self.event_time_maxrange = None

        if self.text.get('$SPILLOVER', None):
            self.fluorescence_compensation()

        for param in self.parameters:
            xn = param.name
            if (('MSW' in param.name.upper()) or ('MSW' in param.short_name.upper())):
                time_msw = param.name
            elif (('LSW' in param.name.upper()) or ('LSW' in param.short_name.upper())):
                time_lsw = param.name

            if param.bit_redux:
                vtrunc = np.vectorize(param.truncate_bits)
                self.xc_df[xn] = vtrunc(self.xc_df[xn])

            if param.log:
                vlog_scale = np.vectorize(param.log_scale)
                self.xc_df[xn] = vlog_scale(self.xc_df[xn])

        self.scale_time(time_msw, time_lsw)
        self.scale_event_count()

    # ------------------------- CSV SUPPORT FILES ------------------------------
    def generate_event_log(self):
        """Extracts some FCS metadata values for use in csv based graphing
            Returns: dict
        """

        attr = [self.file_name,self.sTOT, self.event_time_maxrange,
                self.sSMNO, self.sID, self.sTR, self.ver_id]

        attr_name = ['FILENAME','$TOT', 'MAXTIME',
                     '$SMNO', '$ID', '$TR', 'FCS_VER_ID']

        all_v = self.get_any_SPxX('N', verify_uniform=False)
        all_vn = [s+'-VOLTS' for s in all_v]

        attr_name.extend(all_vn)
        attr.extend(self.get_any_SPxX('V', verify_uniform=False))

        return {self.data_name : dict(zip(attr_name, attr))}


    def generate_data_name(self):
        if self.sID:
            self.data_name = self.file_name.replace('Well_', '')
        else:
            self.data_name = self.file_name

    # --------------------------------------------------------------------------
    def store_csv_data(self, data_folder):
        dcsv = self.data_name + '.csv'
        fn = os.path.join(data_folder, dcsv)
        self.xc_df.to_csv(fn, index=False)
        return fn

    def store_hdf5_data(self, data_folder):
        fn_hdf = self.data_name + '.h5'
        fn = os.path.join(data_folder, fn_hdf)

        self.xc_df.to_hdf(fn, self.data_name, mode='w', complib='zlib', complevel=9)

        return fn_hdf

    # --------------------------------------------------------------------------
