#!/usr/bin/env python3
# -*- coding:utf-8 -*-
# -------------------------------------------------------------------------------------
# Instruction:
#   This script controls measurement instruments via GPIB or Serial interface.
#   It is checked on Mac OSX 10.10, Ubuntu 14.04 LTS(32-bit) and 16.04 LTS (32-bit).
#
# Requirments: (and how to install them on Ubuntu)
#   Connect gpib:
#   - fxload (apt install fxload)
#   - linux-gpib (see linux-gpib official manual)
#   Python API
#   - gpib and Gpib (normally, they are installed when installing linux-gpib)
#   - pyserial (apt install python3-pyserial)
#   - pyvisa and pyvisa-py (apt install python3-pyvisa-py, or, pip3 install pyvisa pyvisa-py)
#   NOTE that gpib and Gpib modules are installed to python2.X site-packages by default.
#   You must build and install them manually to use them on python3. (see linux-gpib.md)
#
# NOTE when using USB - GPIB/serial adapter:
#   - You must connect GPIB/Serial correctly in advance.
#   - Their permissions must be modified as '666' (i.e. run 'sudo chmod 666 /dev/gpib0 /dev/ttyUSB0', to use GPIB-USB and Serial-USB interfaces whose ports are both 0), otherwise a permission error will arise when opening these instruments.
#
# NOTE:
#   - Some warning messages often arise when finishing the script without deleting the ResourceManager instance.
#   - Althogh these warnings are negligible, add 'del <instance_name>' at the end of the script to avoid this .
# -------------------------------------------------------------------------------------

import sys, atexit, time, visa


#------------------------------------------------------------------
# Parental class to control an instrument via GPIB/Serial interface
#------------------------------------------------------------------
class VISA_Instrument(object):
    """
    This class controls instruments via GPIB/serial connection.
    Check the port and address (GPIB only) of the instrument in advance.

    If you use LAN - GPIB/serial interface, use also need
    the ip address of the LAN.

    If you use USB - GPIB/serial adapter to connect them to the computer,
    you need to make connection in advance.
    Use PyVISA (Mac) or Linux-GPIB (Linux) for connection.
    NI-VISA is not supported at the current stage.
    """

    def __init__(self, port=0, address=0, ip=None):
        self.setPort(port)  # GPIB/Serial port
        self.setAddress(address)  # GPIB address
        self.setIP(ip)  # IP address of LAN-GPIB/Serial adapter.
        self.setPyVisaBackend('@py')  # '@py' means using pyvisa-py backend.
        self.updateResourceManager()

    def setPyVisaBackend(self, backend):
        # Run updateResourceManager() to apply the change.
        self.backend = backend

    def updateResourceManager(self):
        self.rm = visa.ResourceManager(self.backend)

    def setPort(self, port):
        self.port = port

    def setAddress(self, address):
        self.address = address

    def setIP(self, ip):
        self.ip = ip

    def openGpib(self):
        if self.ip is None:
            self.inst = self.rm.open_resource(
                'GPIB' + str(self.port) + '::' + str(self.address) + '::INSTR')
        else:
            self.inst = self.rm.open_resource(
                'TCPIP::' + self.ip + '::gpib' + str(self.port) + ',' +
                str(self.address) + '::INSTR')

    def openSerial(self):
        if self.ip is None:
            self.inst = self.rm.open_resource(
                'ASRL/dev/ttyUSB' + str(self.port) + '::INSTR')
        else:
            self.inst = self.rm.open_resource(
                'TCPIP::' + self.ip + '::COM' + str(self.port) + '::INSTR')

    def read(self):
        return self.inst.read()

    def write(self, string):
        self.inst.write(string)
        return

    def query(self, string):
        return self.inst.query(string)

    def getIDN(self):
        self.write("*IDN?")
        return self.read()


#------------------------------------------------------------------
# Instruments inheriting "VISA_Instrument" class
#------------------------------------------------------------------
# GPIB
class Keithley_2602B(VISA_Instrument):
    """
    Source meter
    """

    def __init__(self, port=0, address=26, ip=None):
        super().__init__(port, address, ip)
        self.openGpib()
        atexit.register(self.at_exit)

    def measure_I(self):
        return float(self.query("print(smua.measure.i())"))

    def measure_V(self):
        return float(self.query("print(smua.measure.v())"))

    def measure_R(self):
        return float(self.query("print(smua.measure.r())"))

    def average_R(self, average=100):
        # reset
        self.write("smua.reset()")
        # 4 probe method.
        self.write("smua.sense = smua.SENSE_REMOTE")
        # Voltage source
        self.write("smua.source.func = smua.OUTPUT_DCVOLTS")
        # Source limit (1A).
        self.write("smua.source.limiti = 1")
        # Source range (100 mV)
        self.write("smua.measure.rangev = 100e-3")
        # Set V = 2 mV
        self.write("smua.source.levelv = 2e-3")
        # Output on
        self.write("smua.source.output = smua.OUTPUT_ON")
        R = 0.
        for i in range(average):
            R += self.measure_R()
        return R / average * 1.

    def measure_IV(self, probe=4, output=None):
        # Measurement setting.
        v_end = 10e-3
        step = 150
        # reset
        self.write("smua.reset()")
        #src_mtr.write("smub.reset()")
        if probe == 4:
            # 4 probe method.
            self.write("smua.sense = smua.SENSE_REMOTE")
        elif probe == 2:
            # 2 probe method.
            self.write("smua.sense = smua.SENSE_LOCAL")
        else:
            print("probe must be 2 or 4.")
            sys.exit(1)
        # V
        self.write("smua.source.func = smua.OUTPUT_DCVOLTS")
        # Source limit (10 mV, 10mA).
        # Ignored in IV sweep?
        self.write("smua.source.limitv = 10e-3")
        self.write("smua.source.limiti = 10e-3")
        # Source range (100 mV, 1 mA)
        self.write("smua.measure.rangev = 100e-3")
        self.write("smua.measure.rangei = 5e-3")
        # Timeout (IMPORTANT)
        self.timeout = 100000

        self.write("SweepVLinMeasureI(smua, " + str(-1. * v_end) + "," +
                   str(v_end) + ", 0.001," + str(step) + ")")
        self.write("smua.source.output = smua.OUTPUT_ON")
        self.write("waitcomplete()")
        current = [0 for i in range(step)]
        for i in range(1, step + 1):
            current[i - 1] = self.query("printbuffer(" + str(i) + "," + str(
                i) + ",smua.nvbuffer1.readings)").rstrip()
        if output is None:
            for i in range(0, step):
                print(
                    str(-1. * v_end + v_end * 2. / step * i) + "\t" +
                    str(current[i] if float(current[i]) < 5.0e-3 else "0"))
        else:
            with open(output, 'w') as f:
                for i in range(0, step):
                    f.write(
                        str(-1. * v_end + v_end * 2. / step * i) + "\t" +
                        str(current[i]
                            if float(current[i]) < 5.0e-3 else "0") + '\n')

    def at_exit(self):
        # Turn off output of source meter.
        # It should be registered to "atexit" when connecting this machine
        self.write("smua.source.output = smua.OUTPUT_OFF")


# GPIB
class Lakeshore_LSCI218(VISA_Instrument):
    """
    Thermometer
    """

    def __init__(self, port=0, address=11, ip=None):
        super().__init__(port, address, ip)
        self.openGpib()
        atexit.register(self.at_exit)

    def measure_T(self, num=1):
        # num=2: Inside the dewar
        # num=5: Nine HEB mixers
        return float(self.query("KRDG? " + str(num)))

    def at_exit(self):
        pass


# Serial
class Lakeshore_LSCI218S(VISA_Instrument):
    """
    Thermometer
        - baudrate=300/1200/9600
        - startbits=1
        - databits=7
        - stopbits=1
        - parity=ODD
        - terminator=CR+LF
    """

    def __init__(self, port=0, address=None, ip=None):
        super().__init__(port, address, ip)
        self.openSerial()
        # Tuning serial interface constants
        self.inst.baud_rate = 9600
        self.inst.data_bits = 7
        self.inst.timeout = 1000
        self.inst.parity = visa.constants.Parity.odd
        self.inst.stop_bits = visa.constants.StopBits.one

    def measure_T(self, window=1):
        if window == 0:
            return map(float, (self.query('KRDG? 0')).split(','))
        elif window > 0 and window < 9:
            return float(self.query('KRDG? ' + str(window)))
        else:
            print(
                'Error! num must be 1~8, or 0 to meausre all simultaneously.')


# GPIB
class Agilent_4418B(VISA_Instrument):
    """
    Power meter
    """

    def __init__(self, port=0, address=20, ip=None):
        super().__init__(port, address, ip)
        self.openGpib()
        atexit.register(self.at_exit)

    def at_exit(self):
        pass

    def measure_Power(self, sleep=0.1):
        time.sleep(sleep)
        return float(self.query('MEAS?'))

    def average_Power(self, average=30):
        self.write('*RST')
        self.write('CONF')
        self.write('SENS:AVER ON')
        self.write('SENS:AVER:COUNT:AUTO OFF')
        self.write('SENS:AVER:COUNT ' + str(average))
        return float(self.query('READ?'))


# Serial
class Pfeiffer_TPG262(VISA_Instrument):
    """
     Manometer
        - baudrate=9600
        - startbits=1
        - databits=8
        - paritybits=None
        - stopbits=1
        - terminator=CR+LF
    NOTE that sending '\x05' is necessary to receive data.
    """

    def __init__(self, port=0, address=None, ip=None):
        super().__init__(port, address, ip)
        self.openSerial()
        # Tuning serial interface constants
        self.inst.baud_rate = 9600
        self.inst.data_bits = 8
        self.inst.timeout = 1000
        self.inst.parity = visa.constants.Parity.none
        self.inst.stop_bits = visa.constants.StopBits.one
        self.ENQ = '\x05'

    def measure_Pressure(self):
        self.query('PR1')
        data = self.query(self.ENQ)
        return float(data.split(',')[1].strip())


def measuer_IV_Power(pow_average=30):
    """
    Measure IV curve and IF power simultaneously.
    """
    # Connect
    src_mtr = Keithley_2602B()
    pow_mtr = Agilent_4418B()

    # Initialization
    src_mtr.write("smua.reset()")
    src_mtr.write("smua.sense = smua.SENSE_REMOTE")
    src_mtr.write("smua.source.limitv = 10e-3")
    src_mtr.write("smua.source.limiti = 10e-3")
    src_mtr.write("smua.measure.rangev = 100e-3")
    src_mtr.write("smua.measure.rangei = 5e-3")
    src_mtr.write("smua.source.output = smua.OUTPUT_ON")
    src_mtr.write("waitcomplete()")

    v_end = 9.e-3
    step = 200

    for i in range(step):
        v_bias = -v_end + v_end * 2. / step * i
        # set bias voltage
        src_mtr.write('smua.source.levelv = ' + str(v_bias))
        V = src_mtr.measure_V(src_mtr)
        I = src_mtr.measure_I(src_mtr)
        P = pow_mtr.average_Power(pow_average)
        print(str(V) + " " + str(I) + " " + str(P))
