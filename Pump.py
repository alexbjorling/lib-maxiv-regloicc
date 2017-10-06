import time
import serial
from Communicator import SerialCommunicator, SocketCommunicator

# to do:
#  * the Moxa interface (implement SocketCommunicator)

class Pump(object):
    """
    Class for representing a single Ismatec Reglo ICC multi-channel
    peristaltic pump, controlled over a serial server or direct serial.

    This class directly reflects the Tango interface: public set/get
    methods or properties reflect Tango attributes and others represent
    Tango commands. For channel-dependent properties, the Tango device
    should expose an attribute for each channel. The channel labels are 
    available as self.channels.
    """

    def __init__(self, debug=False, address=None, **kwargs):

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
        self.hw.write('@1')

        # Set everything to default
        self.hw.write('10')

        # Enable independent channel addressing
        self.hw.write('1~1')

        # Get number of channels
        nChannels = int(self.hw.query('1xA'))

        # Enable asynchronous messages
        self.hw.write('1xE1')

        # list of channel indices for iteration and checking
        self.channels = range(1, nChannels+1)

        # initial running states
        self.stop()
        self.hw.setRunningStatus(False, self.channels)

    ####################################################################
    # Properties or setters/getters to be exposed as Tango attributes, #
    # one per channel for the ones that have the channel kwarg.        #
    ####################################################################

    def getPumpVersion(self):
        return self.hw.query('1#').strip()

    def getRunning(self, channel):
        """ 
        Returns True if the specified channels is running
        """
        assert channel in self.channels
        return self.hw.running[channel]

    def getTubingInnerDiameter(self, channel):
        """ 
        Returns the set inner diameter of the peristaltic tubing on the 
        specified channel, in mm.
        """
        assert channel in self.channels
        return float(self.hw.query('%d+'%channel).split(' ')[0])

    def setTubingInnerDiameter(self, diam, channel=None):
        """
        Sets the inner diameter of the peristaltic tubing on the 
        specified channel or on all channels.
        """
        if channel is None:
            allgood = True
            for ch in self.channels:
                allgood = allgood and self.setTubingInnerDiameter(diam, channel=ch)
            return allgood
        return self.hw.write('%d+%s'%(channel, self._discrete2(diam)))

    ###########################################
    # Methods to be exposed as Tango commands #
    ###########################################

    def continuousFlow(self, rate, channel=None): 
        """ 
        Start continuous flow at rate (ml/min) on specified channel or 
        on all channels.
        """
        if channel is None:
            # this enables fairly synchronous start
            channel = 0
            maxrates = []
            for ch in self.channels:
                maxrates.append(float(self.hw.query('%d?'%ch).split(' ')[0]))
            maxrate = min(maxrates)
        else:
            maxrate = float(self.hw.query('%d?'%channel).split(' ')[0])
        assert channel in self.channels or channel == 0
        # flow rate mode
        self.hw.write('%dM'%channel)
        # set flow direction
        if rate < 0:
            self.hw.write('%dK'%channel)
        else:
            self.hw.write('%dJ'%channel)
        # set flow rate
        if abs(rate) > maxrate:
            rate = rate / abs(rate) * maxrate
        self.hw.query('%df%s'%(channel, self._volume2(rate)))
        # make sure the running status gets set from the start to avoid later Sardana troubles
        self.hw.setRunningStatus(True, channel)
        # start
        self.hw.write('%dH'%channel)

    def dispense(self, vol, rate, channel=None):
        """ 
        Dispense vol (ml) at rate (ml/min) on specified channel or on
        all channels.
        """
        if channel is None:
            # this enables fairly synchronous start
            channel = 0
            maxrates = []
            for ch in self.channels:
                maxrates.append(float(self.hw.query('%d?'%ch).split(' ')[0]))
            maxrate = min(maxrates)
        else:
            maxrate = float(self.hw.query('%d?'%channel).split(' ')[0])
        assert channel in self.channels or channel == 0
        # flow rate mode
        self.hw.write('%dO'%channel)
        # make volume positive
        if vol < 0:
            vol *= -1
            rate *= -1
        # set flow direction
        if rate < 0:
            self.hw.write('%dK'%channel)
        else:
            self.hw.write('%dJ'%channel)
        # set flow rate
        if abs(rate) > maxrate:
            rate = rate / abs(rate) * maxrate
        self.hw.query('%df%s'%(channel, self._volume2(rate)))
        # set volume
        self.hw.query('%dv%s'%(channel, self._volume2(vol)))
        # make sure the running status gets set from the start to avoid later Sardana troubles
        self.hw.setRunningStatus(True, channel)
        # start
        self.hw.write('%dH'%channel)

    def stop(self, channel=None):
        """
        Stop any pumping operation on specified channel or on all 
        channels.
        """
        # here we can stop all channels by specifying 0
        channel = 0 if channel is None else channel
        assert channel in self.channels or channel == 0
        # doing this misses the asynchronous stop signal, so set manually
        self.hw.setRunningStatus(False, channel)
        return self.hw.write('%dI'%channel)

    ##########################################
    # Helper methods, not for Tango exposure #
    ##########################################

    def _volume2(self, number):
        # convert number to "volume type 2"
        number = '%.3e'%abs(number)
        number = number[0] + number[2:5] + number[-3] + number[-1]
        return number

    def _volume1(self, number):
        # convert number to "volume type 1"
        number = '%.3e'%abs(number)
        number = number[0] + number[2:5] + 'E' + number[-3] + number[-1]
        return number

    def _discrete2(self, number):
        # convert float to "discrete type 2"
        s = str(number).strip('0')
        whole, decimals = s.split('.')
        return '%04d'%int(whole + decimals)


if __name__ == '__main__':
    """
    Example usage.
    """
    p = Pump(address='/dev/ttyUSB0', debug=True)
    p.setTubingInnerDiameter(3.17)
    p.continuousFlow(rate=25, channel=1)
    p.dispense(vol=1, rate=25, channel=2)
    t0 = time.time()
    while time.time() - t0 < 10:
        print [p.getRunning(channel=i) for i in p.channels]
        time.sleep(.5)
    p.stop()
    print [p.getRunning(channel=i) for i in p.channels]