#### Python GroundSide Front End for the FireSide PCB


#### Library Imports
# Serial and Delays for RYLR Communication
from serial import Serial
from time import sleep
import time
import msvcrt

# Serial COM Port Selection
from serial.tools.list_ports import comports

# Launch Confirmation Sequence Generation
from secrets import choice
from string import ascii_letters, digits, punctuation

# Graceful Script Termination
from sys import exit


#### Display Startup to User
print('\n---')
print(' GroundSide: An Interface to the FireSide PCB')
print('---')


#### Setup COM Port
# Ask User to Select COM Port
print('\nLoaded COM Ports:')
for port in comports():
  print(port)

PortID = input('\nEnter COM Port Number:')

# Check User Input String
try:
  # Verify the Selected Port Exists
  if not (('COM' + PortID) in [port.name for port in comports()]):
    raise IndexError

except IndexError:
  # Notify User of Invalid Input
  print('\n!!!! Invalid COM Port ID Entered: ' + PortID)
  input('!!!! Press Any Key to Exit')
  exit()

# Notify User of Serial Startup
print('\nStarting Serial on COM' + PortID)

# Create and Configure Serial Object for RYLR998
# See REYAX RYLR998 Datasheet for UART Configuration Defaults
RYLR_UART_BAUD = 9600
RYLR = Serial(
  port='COM' + PortID,
  baudrate=RYLR_UART_BAUD,
  timeout=0.1
)


#### Define Interface Layer Functions to RYLR998 Module
# Parses Incoming Data from FireSide PCB via RYLR module
def ParseRYLR() -> str:
  if not RYLR.in_waiting:
    # Return Blank Buffer
    return str('\n')

  # 1. READ: Load Incoming Binary Data
  # 2. DECODE: Decode from bytes to string, IGNORING any bad bytes
  # 3. STRIP: Remove whitespace (like \r\n)
  parsed = RYLR.read_until(b'\n').decode('utf-8', errors='ignore').strip()

  # Check if this is an actual Data Reception message
  if parsed.startswith('+RCV='):
    # Format: +RCV=<Address>,<Length>,<Data>,<RSSI>,<SNR>
    try:
      # Extract Data in 3rd Comma Separated Field
      data = parsed.split(',', maxsplit=4)[2]
      return data  # Return just the payload
    except IndexError:
      # This could happen if the +RCV packet is malformed
      print(f"!!!! Malformed +RCV packet: {parsed}")
      return str('\n')
  
  # If it's not a data packet, it's an AT response (+OK, +ERR, etc.)
  # Return the whole line so it gets printed for debugging.
  if parsed: # Only return if it's not an empty line
    return "-> " + parsed # The "->" helps you see AT responses
  
  return str('\n') # Return blank for empty/unhandled lines
# Sends State Commands to FireSide PCB via RYLR module
def SendRYLR(State : str):
  # Check for Invalid Commands or Switches
  OverrideResponse = False

  # Validate State Command
  if State not in ['SAFE', 'ARM', 'LAUNCH', 'CONVERT']:
    print('\n!!!! Invalid Command To FireSide')
    OverrideResponse = True

  # Confirm Entry into ARM State
  if State == 'ARM':
    # Generate and Output OPT for User
    OTP : str = ''.join(choice( digits
    ) for i in range(4))

    print('\nOTP for ARM State Transition: ' + OTP)

    # Check User Entry Against OTP
    if input('Please Re-enter OTP to Confirm: ') != OTP:
      print('\n!!!! ARM OTP Invalid. Safing FireSide!')
      OverrideResponse = True

  # Confirm Entry into LAUNCH State
  if State == 'LAUNCH':
    # Generate and Output OPT for User
    OTP : str = ''.join(choice( digits
    ) for i in range(4))

    print('\nOTP for LAUNCH State Transition: ' + OTP)

    # Check User Entry Against OTP
    if input('Please Re-enter OTP to Confirm: ') != OTP:
      print('\n!!!! LAUNCH OTP Invalid. Safing FireSide!')
      OverrideResponse = True

  # Issue Send AT Command
  # See +SEND in REYAX AT RYLRX98 Commanding Datasheet
  RYLR.write('AT+SEND=0,'.encode())

  # Default to SAFE State if Above Checks Fail
  if OverrideResponse:
    print('\nSending SAFE Command')

    # Issue Payload Length
    # 4 Characters for SAFE Command
    # Complete Binary Command with Mandatory CRLF Line End
    RYLR.write('4,SAFE\r\n'.encode())
  else:
    # Issue Payload Length
    RYLR.write(str(len(State)).encode())

    # Complete Binary Command with Comma and Mandatory CRLF Line End
    RYLR.write((',' + State + '\r\n').encode())

  return


#### Establish Communication via RYLR module
print('\nEstablishing FireSide Link')

# Prompt User for FireSide PCB Initial State
# Send the Initial State
SendRYLR(input('Choose Initial State (SAFE || CONVERT): '))

# Wait Until FireSide Begins Response to State Command
while not RYLR.in_waiting:
  sleep(0.5)

print('\nFireSide Link Acquired')

#### Start Non-Blocking Main Loop
input_buffer = ""
prompt = "> "
print(prompt, end="", flush=True) # Print the first prompt

#### Start RYLR Communication Loop
while True:
    try:
        # --- 1. Check for Serial Data (Receiving) ---
        # This is non-blocking
        while RYLR.in_waiting:
            line = ParseRYLR()
            if line and line.strip():
                
                # --- This block handles printing data without messing up your typing ---
                # 1. Clear the current line you're typing on
                print(f"\r{' ' * (len(prompt) + len(input_buffer))}\r", end="") 
                
                # 2. Print the received message on its own line
                print(f"{line}")
                
                # 3. Re-print the prompt and whatever you had typed so far
                print(f"{prompt}{input_buffer}", end="", flush=True)


        # --- 2. Check for Keyboard Data (Sending) ---
        # This is non-blocking
        if msvcrt.kbhit():
            # A key has been pressed, get it
            char_bytes = msvcrt.getch()

            try:
                char = char_bytes.decode('utf-8')

                # Check if the user pressed Enter
                if char == '\r': 
                    print() # Move to the next line
                    
                    # Only send if the buffer isn't empty
                    if input_buffer:
                        SendRYLR(input_buffer)
                    
                    # Reset the buffer for the next command
                    input_buffer = ""
                    print(prompt, end="", flush=True) # Print new prompt

                # Check if the user pressed Backspace
                elif char == '\b': 
                    if len(input_buffer) > 0:
                        # Remove last char from buffer and screen
                        input_buffer = input_buffer[:-1]
                        print('\b \b', end="", flush=True) 
                
                # It's a regular character
                else: 
                    input_buffer += char
                    print(char, end="", flush=True) # Echo the character to the screen

            except UnicodeDecodeError:
                # User pressed a special key (like an arrow or F-key)
                # We just ignore it in this simple version
                pass

        # --- 3. Sleep ---
        # This is CRITICAL to prevent 100% CPU usage
        # A small sleep gives the OS time to breathe.
        sleep(0.01) # Sleep for 10 milliseconds

    except KeyboardInterrupt:
        # Allow exiting with Ctrl+C
        print("\nExiting...")
        RYLR.close()
        exit()
