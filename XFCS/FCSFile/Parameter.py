import numpy as np
# ------------------------------------------------------------------------------
def log_lin(f1, f2):
    if (f1 > 0) and (f2 == 0):
        return 1
    else:
        return f2

# ------------------------------------------------------------------------------
class Parameter(object):
    def __init__(self, number, name, short_name, bits, scale, vrange):
        self.number = number
        self.name = name
        self.short_name = short_name
        self.bits = int(bits)
        self.vrange = int(vrange)
        # --------------------- CALCULATED ATTRIBUTES --------------------------
        self.bitrange = (self.vrange - 1).bit_length()
        self.f1 = float(scale.split(',')[0])
        self.f2 = log_lin(self.f1, float(scale.split(',')[1]))
        self.log = (self.f1 + self.f2 != 0)
        self.bit_redux = self.bits - self.bitrange
        self.bit_mask = 2**self.bitrange - 1
        # ---------------------- GRAPH - RANGE ATTR ----------------------------
        self.minrange = 1 if self.log else 0
        self.maxrange = min([self.vrange, 2**self.bits]) - 1
        self.logrange = 10**(self.f1)*self.f2

    def truncate_bits(self, n):
        return self.bit_mask & n

    def log_scale(self, channel_value):
        xs = 10**(self.f1 * channel_value / self.maxrange) * self.f2
        return xs

    def n_log_scale(self, X):
        return 10**(self.f1 * X / self.maxrange) * self.f2

    def archyperbolicsine_scale(self, X):
        return np.log(X + np.sqrt(np.exp2(X) + 1))

    # def check_log(self):
    #     if not self.log:
    #         self.logrange = 0
    #     else:
    #         self.logrange = int(self.logrange)

    # ------------------------------ ATTR LOG ----------------------------------
    def get_attr(self, xc=True, fc=False):
        short = self.short_name

        if fc:
            short += '_FC'

        if xc:
            p_mxrange = self.maxrange
            self.minrange = 0
            p_log = False
        else:
            p_mxrange = self.logrange
            self.minrange = 1
            short += '_XSLOG'
            p_log = self.log

        attr_name = ['short_name', 'log', 'maxrange', 'minrange']
        attr_vals = [short, p_log, p_mxrange, self.minrange]
        return dict(zip(attr_name, attr_vals))

# ------------------------------------------------------------------------------
