import time
import serial

# to do:
#  * status is asynchronous, maybe implement it as a listener. Presumably
#    the pump will only send one message at a time, then the listener
#    could determine whether to hand the message back to the response
#    queue of the Pump class, or whether to use it to set a running flag
#    (&U messages) or take down a running flag (&X messages). The only
#    question is how to handle status response, because these have no \r
#    termination. Maybe the timeout would work. 
#
#  * the Moxa interface

class Communicator(object):
    """
    Base class for communication to Ismatec Reglo ICC over direct serial 
    or through a serial server.
    """

    def __init__(self, debug=False, com=None, socket=None,
                 baudrate=9600, data_bits=8, stop_bits=1, parity='N', timeout=.1):
        """
        kwargs:
        com (int): COM port (like '/dev/ttyUSB0') to use for direct serial
        socket (tuple): (hostname, port) to use for serial server
        baud_rate, data_bits, stop_bits: specific serial settings

        Use write() or query() to write to the specified device.
        """
        self.do_debug = debug

        if com is not None:
            self._commtype = 'serial'
            self.tty = com
            self.write = self._comwrite
            self.query = self._comquery
        elif socket is not None:
            self._commtype = 'socket'
            self.hostname, self.port = socket
            self.write = self._socketwrite
            self.query = self._socketquery
            assert type(self.hostname) == str
            assert type(self.port) == int
        else:
            raise Exception('No communication specified')

        self.serial_details = {'baudrate': baudrate,
                               'bytesize': data_bits,
                               'stopbits': stop_bits,
                               'parity': parity,
                               'timeout': timeout,}

    def _comwrite(self, cmd):
        """
        Writes a command to the device, and returns True if the command
        is accepted, False otherwise.
        """
        with serial.Serial(self.tty, **self.serial_details) as ser:
            self.debug("writing command '%s' to COM %s" % (cmd, self.tty))
            ser.write(cmd + '\r')
            ser.flush()
            result = ser.read(size=1)
        if result == '*':
            return True
        else:
            self.debug('WARNING: command %s returned %s'%(cmd, result))
            return False

    def _comquery(self, cmd):
        """
        Writes a query to the device, and returns the answer.
        """
        with serial.Serial(self.tty, **self.serial_details) as ser:
            self.debug("writing query '%s' to COM %s" % (cmd, self.tty))
            ser.write(cmd + '\r')
            ser.flush()
            result = ser.readline()
            self.debug("got response '%s'"%result.strip())
        return result

    def _socketwrite(self, cmd):
        raise NotImplementedError

    def _socketquery(self, cmd):
        raise NotImplementedError

    def debug(self, msg):
        if self.do_debug:
            print msg


class Pump(Communicator):
    """
    Class for representing a single Ismatec Reglo ICC multi-channel
    peristaltic pump, controlled over a serial server or direct serial.

    This class directly reflects the Tango interface: public set/get
    methods or properties reflect Tango attributes and others represent
    Tango commands. For channel-dependent properties, the Tango device
    should expose an attribute for each channel. The channel labels are 
    available as self.channels.
    """

    def __init__(self, debug=False, **kwargs):
        self.do_debug = debug
        super(Pump, self).__init__(debug=debug, **kwargs)

        # Assign address 1 to pump
        self.write('@1')

        # Set everything to default
        self.write('10')

        # Enable independent channel addressing
        self.write('1~1')

        # Get number of channels
        nChannels = int(self.query('1xA'))

        # Disable asynchronous messages
        self.write('1xE0')

        # list of channel indices for iteration and checking
        self.channels = range(1, nChannels+1)

    ####################################################################
    # Properties or setters/getters to be exposed as Tango attributes, #
    # one per channel for the ones that have the channel kwarg.        #
    ####################################################################

    def getPumpVersion(self):
        return self.query('1#').strip()

    def getRunning(self, channel):
        """ 
        Returns True if the specified channels is running
        """
        assert channel in self.channels
        raise NotImplementedError

    def getFlowRate(self, channel):
        """ 
        Returns the current flow rate on the specified channel, in 
        ml/min.
        """
        assert channel in self.channels
        raise NotImplementedError

    def volume(self, channel):
        """ 
        Returns the current dispensed volume on the specified channel,
        in ml.
        """
        assert channel in self.channels
        raise NotImplementedError

    def getTubingInnerDiameter(self, channel):
        """ 
        Returns the set inner diameter of the peristaltic tubing on the 
        specified channel, in mm.
        """
        assert channel in self.channels
        return float(self.query('%d+'%channel).split(' ')[0])

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
        return self.write('%d+%s'%(channel, self._discrete2(diam)))

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
                maxrates.append(float(self.query('%d?'%ch).split(' ')[0]))
            maxrate = min(maxrates)
        else:
            maxrate = float(self.query('%d?'%channel).split(' ')[0])
        assert channel in self.channels or channel == 0
        # flow rate mode
        self.write('%dM'%channel)
        # set flow direction
        if rate < 0:
            self.write('%dK'%channel)
        else:
            self.write('%dJ'%channel)
        # set flow rate
        if abs(rate) > maxrate:
            rate = rate / abs(rate) * maxrate
        self.write('%df%s'%(channel, self._volume2(rate)))
        # start
        self.write('%dH'%channel)

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
                maxrates.append(float(self.query('%d?'%ch).split(' ')[0]))
            maxrate = min(maxrates)
        else:
            maxrate = float(self.query('%d?'%channel).split(' ')[0])
        assert channel in self.channels or channel == 0
        # flow rate mode
        self.write('%dO'%channel)
        # make volume positive
        if vol < 0:
            vol *= -1
            rate *= -1
        # set flow direction
        if rate < 0:
            self.write('%dK'%channel)
        else:
            self.write('%dJ'%channel)
        # set flow rate
        if abs(rate) > maxrate:
            rate = rate / abs(rate) * maxrate
        self.write('%df%s'%(channel, self._volume2(rate)))
        # set volume
        self.write('%dv%s'%(channel, self._volume2(vol)))
        # start
        self.write('%dH'%channel)

    def stop(self, channel=None):
        """
        Stop any pumping operation on specified channel or on all 
        channels.
        """
        # here we can stop all channels by specifying 0
        channel = 0 if channel is None else channel
        assert channel in self.channels or channel == 0
        return self.write('%dI'%channel)

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
    p = Pump(com='/dev/ttyUSB0', debug=True)
    p.setTubingInnerDiameter(3.17)
    p.continuousFlow(rate=25, channel=1)
    p.dispense(vol=1, rate=25, channel=2)
    time.sleep(10)
    p.stop()