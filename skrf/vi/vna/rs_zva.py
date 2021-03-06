import warnings
from collections import OrderedDict, Iterable

import numpy as np
import skrf
import pyvisa

from . import abcvna
from . import rs_zva_scpi


class ZVA(abcvna.VNA):
    """
    Class for modern Rohde&Schwarz ZVA Vector Network Analyzers
    """

    NAME = "R&S ZVA"
    NPORTS = 4
    NCHANNELS = 32
    SCPI_VERSION_TESTED = 'A.09.20.08'  # taken from PNA class

    def __init__(self, address, **kwargs):
        """
        initialization of ZVA Class

        Parameters
        ----------
        address : str
            visa resource string (full string or ip address)
        kwargs : dict
            interface (str), port (int), timeout (int),
        """
        super(ZVA, self).__init__(address, **kwargs)
        self.resource.timeout = kwargs.get("timeout", 2000)
        self.scpi = rs_zva_scpi.SCPI(self.resource)
        print(self.idn)

    def use_binary(self):
        """setup the analyzer to transfer in binary which is faster, especially
        for large datasets"""
        self.scpi.set_format_binary(ORDER='SWAP')
        self.scpi.set_format_data(DATA='REAL,64')
        self.resource.values_format.use_binary(datatype='d',
                                               is_big_endian=False,
                                               container=np.array)

    def use_ascii(self):
        self.scpi.set_format_data(DATA='ASCII')
        self.resource.values_format.use_ascii(converter='f', separator=',',
                                              container=np.array)

    @property
    def echo(self):
        return self.scpi.echo

    @echo.setter
    def echo(self, onoff):
        if onoff in (1, True):
            self.scpi.echo = True
        elif onoff in (0, False):
            self.scpi.echo = False
        else:
            raise warnings.warn("echo must be a boolean")

    @property
    def active_channel(self):
        old_timeout = self.resource.timeout
        self.resource.timeout = 500
        try:
            channel = self.scpi.query_active_channel()
        except pyvisa.VisaIOError:
            print("No channel active, using 1")
            channel = 1
        finally:
            self.resource.timeout = old_timeout
        return channel

    @active_channel.setter
    def active_channel(self, channel):
        """
        Set the active channel on the analyzer

        Parameters
        ----------
        channel : int

        Notes
        -----
        """
        old_timeout = self.resource.timeout
        self.resource.timeout = 500
        if channel in self.channel_list:
            self.scpi.set_active_channel(channel)
        else:
            print('Channel %i not in list of channels. Create channel first'
                  % channel)
        return self.scpi.query_active_channel()

    @property
    def channel_list(self):
        """Return list of channels"""
        return_str = self.scpi.query_channel_catalog().split(',')
        channel_dct = {}
        for i in range(int(len(return_str)/2)):
            channel_dct[int(return_str[2 * i])] = return_str[2 * i + 1]
        return channel_dct

    def get_frequency(self, **kwargs):
        """
        get an skrf.Frequency object for the current channel

        Parameters
        ----------
        kwargs : dict
            channel (int), f_unit (str)

        Returns
        -------
        skrf.Frequency
        """
        #self.resource.clear()
        channel = kwargs.get("channel", self.active_channel)
        use_log = "LOG" in self.scpi.query_sweep_type(channel).upper()
        f_start = self.scpi.query_f_start(channel)
        f_stop = self.scpi.query_f_stop(channel)
        f_npoints = self.scpi.query_sweep_n_points(channel)
        if use_log:
            freq = np.logspace(np.log10(f_start), np.log10(f_stop), f_npoints)
        else:
            freq = np.linspace(f_start, f_stop, f_npoints)

        frequency = skrf.Frequency.from_f(freq, unit="Hz")
        frequency.unit = kwargs.get("f_unit", "Hz")
        return frequency

    def set_frequency_sweep(self, f_start, f_stop, f_npoints, **kwargs):
        f_unit = kwargs.get("f_unit", "hz").lower()
        if f_unit != "hz":
            f_start = self.to_hz(f_start, f_unit)
            f_stop = self.to_hz(f_stop, f_unit)
        channel = kwargs.get("channel", self.active_channel)
        self.scpi.set_f_start(channel, f_start)
        self.scpi.set_f_stop(channel, f_stop)
        self.scpi.set_sweep_n_points(f_npoints)

