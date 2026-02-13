import serial
import struct
import time
import csv

COM_PORT = "COM7"
BAUD_RATE = 921600
BUFFER_SIZE = 4096

MAGIC_WORD = b"\x02\x01\x04\x03\x06\x05\x08\x07"
MAGIC_WORD_LEN = 8
DETECTED_OBJ_TLV_TYPE = 6

CSV_FILE = "radar_decimal_output.csv"


# ----------------------------------------------------------
# Open Serial Port
# ----------------------------------------------------------
def open_serial_port():
    try:
        ser = serial.Serial(
            port=COM_PORT,
            baudrate=BAUD_RATE,
            bytesize=serial.EIGHTBITS,
            parity=serial.PARITY_NONE,
            stopbits=serial.STOPBITS_ONE,
            timeout=0.05
        )
        print(f"Opened {COM_PORT}")
        return ser
    except Exception as e:
        print("ERROR opening port:", e)
        return None


# ----------------------------------------------------------
# Save DECIMAL values to CSV file
# ----------------------------------------------------------
def save_to_csv(decimal_list):
    with open(CSV_FILE, "a", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(decimal_list)


# ----------------------------------------------------------
# Print only decimal values (no hex, no ascii)
# ----------------------------------------------------------
def print_decimal_data(buffer):
    print("\nDecimal Bytes:")
    for i in range(0, len(buffer), 16):
        chunk = buffer[i:i + 16]
        decimals = [b for b in chunk]

        # Print decimal values
        print(decimals)

        # Save to CSV
        save_to_csv(decimals)


# ----------------------------------------------------------
# Find magic word in a byte buffer
# ----------------------------------------------------------
def find_magic_word(buf):
    for i in range(len(buf) - MAGIC_WORD_LEN):
        if buf[i:i + MAGIC_WORD_LEN] == MAGIC_WORD:
            return i
    return -1


# ----------------------------------------------------------
# Parse TLVs
# ----------------------------------------------------------
def parse_tlvs(data, num_tlvs, num_detected_obj):
    offset = 0
    for tlv_index in range(num_tlvs):

        if offset + 8 > len(data):
            return

        tlv_type, tlv_length = struct.unpack_from("<II", data, offset)
        offset += 8

        if tlv_type == DETECTED_OBJ_TLV_TYPE:
            print(f"Detected Objects: {num_detected_obj}")

            obj_struct_size = 16  # 4 floats

            for i in range(num_detected_obj):
                start = offset + i * obj_struct_size
                if start + obj_struct_size > len(data):
                    break

                x, y, z, v = struct.unpack_from("<ffff", data, start)
                print(f"  Obj {i+1}: X={x:.2f}, Y={y:.2f}, Z={z:.2f}, V={v:.2f}")

        offset += (tlv_length - 8)


# ----------------------------------------------------------
# Parse Frame
# ----------------------------------------------------------
def parse_frame(frame):
    header_format = "<IIIIIIII"
    header_size = struct.calcsize(header_format)

    if len(frame) < header_size:
        return

    version, totalPacketLen, platform, frameNumber, \
    timeCpuCycles, numDetectedObj, numTLVs, subFrameNumber = \
        struct.unpack_from(header_format, frame, 0)

    print(f"\n=== Frame {frameNumber} ===")
    print(f"Detected: {numDetectedObj}   TLVs: {numTLVs}")

    tlv_start = frame[header_size:]
    parse_tlvs(tlv_start, numTLVs, numDetectedObj)


# ----------------------------------------------------------
# Main Loop
# ----------------------------------------------------------
def main():
    ser = open_serial_port()
    if ser is None:
        return

    print(f"Saving decimal byte stream to: {CSV_FILE}")

    while True:
        try:
            data = ser.read(BUFFER_SIZE)

            if len(data) == 0:
                continue

            print_decimal_data(data)

            idx = find_magic_word(data)

            if idx >= 0 and (len(data) - idx) > 40:
                frame_start = data[idx + MAGIC_WORD_LEN:]
                parse_frame(frame_start)

        except KeyboardInterrupt:
            print("\nStopped by user.")
            break
        except Exception as e:
            print("Error:", e)

        time.sleep(0.05)

    ser.close()


if __name__ == "__main__":
    main()