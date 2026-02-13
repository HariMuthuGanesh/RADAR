import serial
import struct
import time

COM_PORT = "COM7"     # Change to your COM port
BAUD_RATE = 921600

MAGIC_WORD = b'\x02\x01\x04\x03\x06\x05\x08\x07'
MAGIC_LEN = 8

def find_magic_word(buffer):
    """Return index of magic word or -1."""
    for i in range(len(buffer) - MAGIC_LEN):
        if buffer[i:i + MAGIC_LEN] == MAGIC_WORD:
            return i
    return -1


def print_raw_decimal(data):
    """Print raw frame bytes in decimal."""
    print("\n--- RAW DATA IN DECIMAL ---")
    for i in range(0, len(data), 16):
        chunk = data[i:i + 16]
        print(f"{i:04d}: ", end="")
        for b in chunk:
            print(f"{b:03d} ", end="")
        print()
    print("---------------------------\n")


def parse_frame(frame):
    """Parse mmWave TLV frame."""
    header_format = "<IIIIIIII"  # 8 unsigned ints
    header_size = struct.calcsize(header_format)

    if len(frame) < header_size:
        print("Frame too small")
        return

    header = struct.unpack(header_format, frame[:header_size])

    version, totalPacketLen, platform, frameNumber, timeCpuCycles, \
    numDetectedObj, numTLVs, subFrameNumber = header

    print(f"\n===== FRAME {frameNumber} =====")
    print(f"Version: {version}")
    print(f"Total Packet Len: {totalPacketLen}")
    print(f"Detected Objects: {numDetectedObj}")
    print(f"Num TLVs: {numTLVs}\n")

    offset = header_size

    # PROCESS EACH TLV
    for _ in range(numTLVs):
        tlv_type, tlv_length = struct.unpack("<II", frame[offset:offset + 8])
        offset += 8

        if tlv_type == 6:    # DETECTED OBJECTS
            print(f"TLV TYPE = 6 (Detected Objects)")

            obj_struct = "<ffff"   # x, y, z, velocity (floats)
            obj_size = struct.calcsize(obj_struct)

            for i in range(numDetectedObj):
                start = offset + i * obj_size
                end = start + obj_size

                if end > len(frame):
                    break

                x, y, z, v = struct.unpack(obj_struct, frame[start:end])
                print(f" Object {i+1}: X={x:.2f}, Y={y:.2f}, Z={z:.2f}, V={v:.2f}")

        offset += tlv_length - 8


def main():
    print(f"Opening serial port {COM_PORT} ...")

    ser = serial.Serial(COM_PORT, BAUD_RATE,
                        timeout=0.1)

    while True:
        data = ser.read(4096)

        if not data:
            continue

        print_raw_decimal(data)

        idx = find_magic_word(data)

        if idx >= 0:
            print(f"MAGIC WORD FOUND at index {idx}: ", list(data[idx:idx + 8]))

            # Frame starts AFTER magic word
            frame = data[idx + MAGIC_LEN:]

            if len(frame) > 40:
                parse_frame(frame)

        time.sleep(0.05)
        
if __name__ == "__main__":
    main()
