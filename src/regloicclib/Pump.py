"""A single Ismatec Reglo ICC multi-channel peristaltic pump, class and usage example."""
from .Communicator import SerialCommunicator, SocketCommunicator


class Pump(object):
    """
    Class for representing a single Ismatec Reglo ICC multi-channel peristaltic pump.

    It can be controlled over a serial server (gateway) or direct serial.

    This class directly reflects the Tango interface: public set/get
    methods or properties reflect Tango attributes and others represent
    Tango commands. For channel-dependent properties, the Tango device
    should expose an attribute for each channel. The channel labels are
    available as self.channels.
    """

    def __init__(self, debug=False, address=None, **kwargs):
        """Initialize the Communicator and setup the pump to accept commands."""
        # make a hardware Communicator object
        if type(address) == str:
            # serial
            self.hw = SerialCommunicator(address=address, debug=debug, **kwargs)
        elif type(address) == tuple and len(address) == 2:
            # socket
            self.hw = SocketCommunicator(address=address, debug=debug, **kwargs)
        else:
            raise RuntimeError('Specify serial device or (host, port) tuple!')
        self.hw.start()

        # Assign address 1 to pump
        self.hw.command(b'@1')

        # Set everything to default
        self.hw.command(b'10')

        # Enable independent channel addressing
        self.hw.command(b'1~1')

        # Get number of channels
        try:
            nChannels = int(self.hw.query(b'1xA'))
        except ValueError:
            nChannels = 0

        # Enable asynchronous messages
        self.hw.command(b'1xE1')

        # list of channel indices for iteration and checking
        self.channels = list(range(1, nChannels + 1))

        # initial running states
        self.stop()
        self.hw.setRunningStatus(False, self.channels)

    ####################################################################
    # Properties or setters/getters to be exposed as Tango attributes, #
    # one per channel for the ones that have the channel kwarg.        #
    ####################################################################

    def getPumpVersion(self):
        """Return the pump model, firmware version, and pump head type code."""
        return self.hw.query(b'1#').strip()

    def getFlowrate(self, channel):
        """Return the current flowrate of the specified channel."""
        assert channel in self.channels
        reply = self.hw.query(b'%df' % channel)
        return float(reply) if reply else 0

    def getRunning(self, channel):
        """Return True if the specified channel is running."""
        assert channel in self.channels
        return self.hw.running[channel]

    def getTubingInnerDiameter(self, channel):
        """Return the set peristaltic tubing inner diameter on the specified channel, in mm."""
        assert channel in self.channels
        return float(self.hw.query(b'%d+' % channel).split(' ')[0])

    def setTubingInnerDiameter(self, diam, channel=None):
        """
        Set the peristaltic tubing inner diameter on the specified channel, in mm.

        If no channel is specificed, set it on all channels.
        """
        if channel is None:
            allgood = True
            for ch in self.channels:
                allgood = allgood and self.setTubingInnerDiameter(diam, channel=ch)
            return allgood
        return self.hw.command(b'%d+%s' % (channel, self._discrete2(diam).encode()))

    ###########################################
    # Methods to be exposed as Tango commands #
    ###########################################

    def continuousFlow(self, rate, channel=None):
        """
        Start continuous flow at rate (ml/min) on specified channel.

        If no channel is specified, start flow on all channels.
        """
        if channel is None:
            # this enables fairly synchronous start
            channel = 0
            maxrates = []
            for ch in self.channels:
                maxrates.append(float(self.hw.query(b'%d?' % ch).split(' ')[0]))
            maxrate = min(maxrates)
        else:
            maxrate = float(self.hw.query(b'%d?' % channel).split(' ')[0])
        assert channel in self.channels or channel == 0
        # flow rate mode
        self.hw.command(b'%dM' % channel)
        # set flow direction.  K=clockwise, J=counterclockwise
        if rate < 0:
            self.hw.command(b'%dK' % channel)
        else:
            self.hw.command(b'%dJ' % channel)
        # set flow rate
        if abs(rate) > maxrate:
            rate = rate / abs(rate) * maxrate
        self.hw.query(b'%df%s' % (channel, self._volume2(rate).encode()))
        # make sure the running status gets set from the start to avoid later Sardana troubles
        self.hw.setRunningStatus(True, channel)
        # start
        self.hw.command(b'%dH' % channel)

    def dispense(self, vol, rate, channel=None):
        """
        Dispense vol (ml) at rate (ml/min) on specified channel.

        If no channel is specified, dispense on all channels.
        """
        if channel is None:
            # this enables fairly synchronous start
            channel = 0
            maxrates = []
            for ch in self.channels:
                maxrates.append(float(self.hw.query(b'%d?' % ch).split(' ')[0]))
            maxrate = min(maxrates)
        else:
            maxrate = float(self.hw.query(b'%d?' % channel).split(' ')[0])
        assert channel in self.channels or channel == 0
        # flow rate mode
        self.hw.command(b'%dO' % channel)
        # make volume positive
        if vol < 0:
            vol *= -1
            rate *= -1
        # set flow direction
        if rate < 0:
            self.hw.command(b'%dK' % channel)
        else:
            self.hw.command(b'%dJ' % channel)
        # set flow rate
        if abs(rate) > maxrate:
            rate = rate / abs(rate) * maxrate
        self.hw.query(b'%df%s' % (channel, self._volume2(rate).encode()))
        # set volume
        self.hw.query(b'%dv%s' % (channel, self._volume2(vol).encode()))
        # make sure the running status gets set from the start to avoid later Sardana troubles
        self.hw.setRunningStatus(True, channel)
        # start
        self.hw.command(b'%dH' % channel)

    def stop(self, channel=None):
        """
        Stop any pumping operation on specified channel.

        If no channel is specified, stop on all channels.
        """
        # here we can stop all channels by specifying 0
        channel = 0 if channel is None else channel
        assert channel in self.channels or channel == 0
        # doing this misses the asynchronous stop signal, so set manually
        self.hw.setRunningStatus(False, channel)
        return self.hw.command(b'%dI' % channel)

    ##########################################
    # Helper methods, not for Tango exposure #
    ##########################################

    def _volume2(self, number):
        # convert number to "volume type 2"
        number = '%.3e' % abs(number)
        number = number[0] + number[2:5] + number[-3] + number[-1]
        return number

    def _volume1(self, number):
        # convert number to "volume type 1"
        number = '%.3e' % abs(number)
        number = number[0] + number[2:5] + 'E' + number[-3] + number[-1]
        return number

    def _discrete2(self, number):
        # convert float to "discrete type 2"
        s = str(number).strip('0')
        whole, decimals = s.split('.')
        return '%04d' % int(whole + decimals)


def example_usage():
    """Provide an example usage."""
    import time
    # p = Pump(address='/dev/ttyUSB0', debug=True)
    p = Pump(address=('b-nanomax-pump-tmpdev-0', 4001), debug=True, timeout=.2)
    p.setTubingInnerDiameter(3.17)
    p.continuousFlow(rate=25, channel=1)
    p.dispense(vol=1, rate=25, channel=2)
    t0 = time.time()
    while time.time() - t0 < 10:
        print([p.getRunning(channel=i) for i in p.channels])
        time.sleep(.5)
    p.stop()
    print([p.getRunning(channel=i) for i in p.channels])
