import time

class SerialDevice(object):
    """
    Base class for communication to the device over serial or through a
    serial Moxa server.
    """

    def __init__(self, com=None, socket=None):
        """
        kwargs:
        com (int): COM port to use for direct serial
        socket (tuple): (hostname, port) to use for serial server

        Use write() and read() to write to the specified device.
        """
        if com is not None:
            self._commtype = 'serial'
            self.com = com
            self.write = self._comwrite
            self.read = self._comread
            assert type(self.com) == int
        elif socket is not None:
            self._commtype = 'socket'
            self.hostname, self.port = socket
            self.write = self._socketwrite
            self.read = self._socketread
            assert type(self.hostname) == str
            assert type(self.port) == int
        else:
            raise Exception('No communication specified')

    def _socketwrite(self, cmd):
        print "dummy-writing command '%s' to %s:%d" % (cmd, self.hostname, self.port)

    def _comwrite(self, cmd):
        print "dummy-writing command '%s' to COM %d" % (cmd, self.com)

    def _socketread(self):
        print "dummy-reading from %s:%d" % (self.hostname, self.port)

    def _comread(self):
        print "dummy-reading from COM %d" % (self.com)


class Pump(SerialDevice):
    """
    Class for representing a single Ismatec Reglo ICC multi-channel
    peristaltic pump, controlled over a serial server or direct serial.

    This class directly reflects the Tango interface: public set/get
    methods or properties reflect Tango attributes and others represent
    Tango commands. For channel- dependent properties, the Tango device
    should expose an attribute for each channel.
    """

    def __init__(self, nChannels=2, **kwargs):
        super(Pump, self).__init__(**kwargs)

        # list of channel indices for iteration and checking
        self.channels = range(nChannels)

    #############################################################
    # Properties or setters/getters exposed as Tango attributes #
    #############################################################

    def getRunning(self, channel):
        """ 
        Returns True if the specified channels is running
        """
        return False

    def getFlowRate(self, channel):
        """ 
        Returns the current flow rate on the specified channel, in 
        ml/min.
        """
        return 0.0

    def volume(self, channel):
        """ 
        Returns the current dispensed volume on the specified channel,
        in ml.
        """
        return 0.0

    def getTubingInnerDiameter(self, channel):
        """ 
        Returns the set inner diameter of the peristaltic tubing on the 
        specified channel, in mm.
        """
        return 3.14

    def setTubingInnerDiameter(self, diam, channel=None):
        """
        Sets the inner diameter of the peristaltic tubing on the 
        specified channel or on all channels.
        """
        if channel is None:
            for ch in self.channels:
                self.tubingInnerDiameter(diam, channel=ch)
        return True

    #####################################
    # Methods exposed as Tango commands #
    #####################################

    def continuousFlow(self, rate, channel=None): 
        """ 
        Start continuous flow at rate (ml/min) on specified channel or 
        on all channels.
        """
        if channel is None:
            for ch in self.channels:
                self.continuousFlow(rate, channel=ch)
            return True
        self.write('pump commands to start ch %d at %.1f ml/min'%(channel, rate))
        return True

    def dispense(self, vol, rate, channel=None):
        """ 
        Dispense vol (ml) at rate (ml/min) on specified channel or on
        all channels.
        """
        if channel is None:
            for ch in self.channels:
                self.dispense(vol, rate, channel=ch)
            return True
        self.write('pump commands to dispense ch %d %.1f ml at %.1f ml/min'%(channel, vol, rate))
        return True

    def stop(self, channel=None):
        """
        Stop any pumping operation on specified channel or on all 
        channels.
        """
        if channel is None:
            for ch in self.channels:
                self.stop(channel=ch)
            return True
        self.write('pump commands to stop ch %d'%channel)
        return True

if __name__ == '__main__':
    p = Pump(socket=('hostname.maxiv.lu.se', 1234))
    p.dispense(15, 30)
    time.sleep(2)
    p.stop()
