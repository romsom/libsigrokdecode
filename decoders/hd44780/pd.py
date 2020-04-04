import sigrokdecode as srd
from functools import reduce 

class PIN:
    RS, CLK, BIT_4, BIT_5, BIT_6, BIT_7, RW, BIT_0, BIT_1, BIT_2, BIT_3 = range(11)

class ANN:
    CLEAR, HOME, ENTRY_MODE, DISPLAY_CONTROL, DISPLAY_SHIFT, FUNCTION_SET, SET_CGRAM_ADDR, SET_DDRAM_ADDR, READ_BF_AC, MEM_WRITE, MEM_READ, STATE, WARNING = range(13)

class Decoder(srd.Decoder):
    api_version = 3
    id = 'hd44780'
    name = 'HD44780'
    longname = 'Hitachi HD44780'
    desc = 'Standard LCD controller protocol'
    license = 'gplv2+'
    inputs = ['logic']
    outputs = []
    channels = (
        {'id': 'rs', 'name': 'RS', 'desc': 'Register select'},
        {'id': 'clk', 'name': 'CLK', 'desc': 'Clock'},
        {'id': 'bit_4', 'name': 'BIT_4', 'desc': 'Data bit 4'},
        {'id': 'bit_5', 'name': 'BIT_5', 'desc': 'Data bit 5'},
        {'id': 'bit_6', 'name': 'BIT_6', 'desc': 'Data bit 6'},
        {'id': 'bit_7', 'name': 'BIT_7', 'desc': 'Data bit 7'},
    )
    optional_channels = (
        {'id': 'rw', 'name': 'R/W', 'desc': 'Read/Write select'},
        {'id': 'bit_0', 'name': 'BIT_0', 'desc': 'Data bit 0, unused in 4-bit mode'},
        {'id': 'bit_1', 'name': 'BIT_1', 'desc': 'Data bit 1, unused in 4-bit mode'},
        {'id': 'bit_2', 'name': 'BIT_2', 'desc': 'Data bit 2, unused in 4-bit mode'},
        {'id': 'bit_3', 'name': 'BIT_3', 'desc': 'Data bit 3, unused in 4-bit mode'},
    )
    options = (
        {'id': 'mode', 'desc': 'Data access mode', 'default': '8bit', 'values': ('8bit', '4bit')},
    )
    annotations = (
        ('clear', 'Clear display'),
        ('home', 'Cursor home'),
        ('entry_mode', 'Entry mode'),
        ('display_control', 'Display control'),
        ('diplay_shift', 'Display shift'),
        ('function_set', 'Function set'),
        ('set_cgram_addr', 'Set CGRAM address'),
        ('set_ddram_addr', 'Set DDRAM address'),
        ('read_bf_ac', 'Read busy flag and address counter'),
        ('mem_write', 'Write to CGRAM or DDRAM'),
        ('mem_read', 'Read from CGRAM or DDRAM'),
        ('state', 'Controller state'),
        ('warning', 'Warning')
    )
    annotation_rows = (
        ('command', 'Command', (0, 1, 2, 3, 4, 5, 6, 7, 8)),
        ('mem_access', 'Memory access', (9, 10)),
        ('state', 'State', (11,)),
        ('warnings', 'Warnings', (12,)),
    )

    def __init__(self, **kwargs):
        self.reset()

    def reset(self):
        pass

    def start(self):
        self.out_ann = self.register(srd.OUTPUT_ANN)

    # TODO
    def metadata(self, key, value):
        if key == srd.SRD_CONF_SAMPLERATE:
            self.samplerate = value

    def decode_pins(self, pins):
        data = [pins[i] if pins[i] in (0, 1)
                else 0 for i in [PIN.BIT_0, PIN.BIT_1, PIN.BIT_2, PIN.BIT_3,
                                 PIN.BIT_4, PIN.BIT_5, PIN.BIT_6, PIN.BIT_7]]
        val = reduce(lambda a, b: (a << 1) | b, reversed(data))
        return val

    def basic_annotation(self, n_ann, further_description = []):
        basic_ann_desc = self.annotations[n_ann][1]
        # build array with annotation description from decoder definition in two forms
        return [n_ann, [basic_ann_desc] + further_description + [basic_ann_desc[:1]]]

    def decode_write_command(self, val):
        ann = self.basic_annotation(ANN.WARNING, ['{:8b}: Unknown command'.format(val)])
        if val < (1<<1): # clear
            ann = self.basic_annotation(ANN.CLEAR, ['Clr'])
        elif val < (1<<2): # home
            ann = self.basic_annotation(ANN.HOME, ['CH'])
        elif val < (1<<3): # entry mode set
            inc = 'inc' if (val & 0x1) != 0 else 'dec'
            shift = 'true' if (val & 0x0) != 0 else 'false'
            ann = [ANN.ENTRY_MODE,
                   ['Entry mode: direction: {}, shift: {}'.format(inc, shift),
                    'Dir: {}, shift: {}'.format(inc, shift),
                    '{}, {}'.format(inc, shift),
                    '{}, {}'.format(inc[0], shift[0])]]
        elif val < (1<<4): # display control
            # TODO
            ann = self.basic_annotation(ANN.DISPLAY_CONTROL, ['Display control: <not implemented>'])
            pass
        elif val < (1<<5): # display shift
            # TODO
            ann = self.basic_annotation(ANN.DISPLAY_SHIFT, ['Display shift: <not implemented>'])
            pass
        elif val < (1<<6): # function set
            # TODO
            if val & (1 << 4) != 0:
                self.state = '8bit'
                ann = self.basic_annotation(ANN.FUNCTION_SET, ['Function Set: 8 bit mode'])
            else:
                self.state = '4bit_first_nibble'
                ann = self.basic_annotation(ANN.FUNCTION_SET, ['Function Set: 4 bit mode'])
                
        elif val < (1<<7): # set cgram addr
            # TODO
            ann = self.basic_annotation(ANN.SET_CGRAM_ADDR, ['Set CGRAM Address: 0x{:2x}'.format(val & 0x3f)])
            pass
        else: # set ddram addr
            # TODO
            ann = self.basic_annotation(ANN.SET_DDRAM_ADDR, ['Set DDRAM Address: 0x{:2x}'.format(val & 0x7f)])
            pass
        return ann
            
    def decode(self):
        if self.options['mode'] == '8bit':
            self.state = '8bit'
        elif self.options['mode'] == '4bit':
            self.state = '4bit_first_nibble'
        cmd = 0
        ann = []
        while True:
            pins = self.wait({PIN.CLK: 'f'})
            if self.state == '8bit':
                start_sample = self.samplenum
                val = self.decode_pins(pins)

            elif self.state == '4bit_first_nibble':
                start_sample = self.samplenum
                pins_first_half = pins # for consistency checking
                val_first_half = self.decode_pins(pins)
                self.state = '4bit_second_nibble'
                self.wait({PIN.CLK: 'r'})
                continue

            elif self.state == '4bit_second_nibble':
                # we can set state here, but a command might change it later
                val_second_half = self.decode_pins(pins)
                val = (val_second_half >> 4) + val_first_half
                self.state = '4bit_first_nibble'
                
            else: # ignore
                self.wait({PIN.CLK: 'r'})
                continue

            if pins[PIN.RS] == 0: # command
                if pins[PIN.RW] == 1: # read
                    # TODO: contents
                    # Wikipedia says delay is 0µs here
                    ann = self.basic_annotation(ANN.READ_BF_AC)
                else: # write
                    ann = self.decode_write_command(val)
            else:
                if pins[PIN.RW] == 1: # memory read
                    # TODO: timings: wait 37µs
                    ann = [ANN.MEM_READ, ["Read: <not implemented>"]]
                else: # memory write
                    ann = [ANN.MEM_WRITE, ["Write: 0x{:x}, '{:c}'".format(val, val),
                                           "'{:c}'".format(val)]]
            self.wait({PIN.CLK: 'r'})
            end_sample = self.samplenum
            self.put(start_sample, end_sample, self.out_ann, ann)
