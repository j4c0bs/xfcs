
# ------------------------------------------------------------------------------
def x_endian(byte_ord):
    """Determines data byte order based on fcs file format specifications.

    Arg:
        byte_ord: fcs text section value for $BYTEORD

    Returns:
        str: little | big - for use in DataSection.

    Raises:
        ValueError - file spec provides only 2 options for this parameter.
    """

    if byte_ord == '1,2,3,4':
        return 'little'
    elif byte_ord == '4,3,2,1':
        return 'big'
    else:
        raise ValueError


# ------------------------------------------------------------------------------
class Metadata(object):
    def __init__(self, text):
        """Initialize metadata section for FCS File"""
        self.spec = None
        self.channels = {}
        self.parse_text(text)


    def __prep_required_spec(self, text):
        spec_names = ('type', 'mode', 'byteorder', 'PAR', 'TOT')
        spec_keys = ('$DATATYPE', '$MODE', '$BYTEORD', '$PAR', '$TOT')
        spec_types = (str, str, x_endian, int, int)
        spec_vals = [text[key] for key in spec_keys]
        md_vals = [format_type(v) for (format_type, v) in zip(spec_types, spec_vals)]

        self.spec = dict(zip(spec_names, md_vals))
        self.spec['timestep'] = float(text.get('$TIMESTEP', 0))
        self.spillover = text.get('$SPILLOVER', None)


    def __get_channel_attributes(self, text):
        attr_sfx = ['N','S','B','E','R']
        num_params = self.spec['PAR']
        self.channel_names = []
        self.byte_check = []

        for n in range(1, num_params + 1):
            param_n = [text['$P'+str(n)+A] for A in attr_sfx]
            self.channel_names.append(param_n[0])
            self.byte_check.append(int(param_n[2]))
            self.channels[n] = param_n


    def parse_text(self, text):
        self.__prep_required_spec(text)
        self.__get_channel_attributes(text)


    def verify_format(self, data_len):
        byte_set = set(self.byte_check)
        byte_len = list(byte_set)[0]

        if len(byte_set) > 1:
            print('DATA BYTE READ LENGTH NOT STANDARD FOR ALL CHANNELS')
            return False
        elif byte_len % 8 != 0:
            print('DATA BYTE READ LENGTH NOT RECOGNIZED: {}'.format(byte_len))
            return False
        else:
            self.spec.update({'byte_len':byte_len})

        if self.spec['mode'] != 'L':
            print('FCS MODE NOT SUPPORTED - LIST MODE ONLY')
            return False
        elif self.spec['type'] != 'I':
            print('FCS DATA TYPE NOT SUPPORTED')
            return False
        elif data_len != (self.spec['PAR'] * self.spec['TOT'] * (byte_len // 8)):
            print('UNABLE TO READ FCS DATA SECTION')
            return False

        return True


# ------------------------------------------------------------------------------
