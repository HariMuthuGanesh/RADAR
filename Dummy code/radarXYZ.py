import serial
import struct
import time

COM_PORT = "COM7"
BAUD = 921600
MAGIC = b"\x02\x01\x04\x03\x06\x05\x08\x07"
MAGIC_LEN = len(MAGIC)

DETECTED_OBJ_TLV_TYPE = 6

HEADER_STRUCT = "<IIIIIIII"      # 8 uint32 fields
TLV_HEADER_STRUCT = "<II"        # type length
OBJ_STRUCT = "<ffff"             # x y z velocity


def find_magic(buf):
    for i in range(len(buf) - MAGIC_LEN):
        if buf[i:i + MAGIC_LEN] == MAGIC:
            return i
    return -1


def parse_tlvs(data, num_tlvs, num_objects):
    offset = 0
    objects = []

    for _ in range(num_tlvs):
        tlv_type, tlv_len = struct.unpack_from(TLV_HEADER_STRUCT, data, offset)
        offset += struct.calcsize(TLV_HEADER_STRUCT)

        if tlv_type == DETECTED_OBJ_TLV_TYPE:
            for i in range(num_objects):
                x, y, z, v = struct.unpack_from(OBJ_STRUCT, data, offset + i * struct.calcsize(OBJ_STRUCT))
                objects.append((x, y, z, v))
        offset += tlv_len - struct.calcsize(TLV_HEADER_STRUCT)

    return objects


def parse_frame(frame):
    header_size = struct.calcsize(HEADER_STRUCT)
    header = struct.unpack_from(HEADER_STRUCT, frame, 0)

    version, total_len, platform, frame_number, cpu, num_obj, num_tlvs, subframe = header

    print("Frame", frame_number)
    print("Objects", num_obj)

    body = frame[header_size:]
    objects = parse_tlvs(body, num_tlvs, num_obj)

    for idx, (x, y, z, v) in enumerate(objects, 1):
        print(f"Object {idx} X {x:.2f}  Y {y:.2f}  Z {z:.2f}  V {v:.2f}")

    return objects


def main():
    ser = serial.Serial(COM_PORT, BAUD, timeout=0.1)
    print("Reading frames")

    while True:
        data = ser.read(4096)
        if not data:
            continue

        idx = find_magic(data)
        if idx >= 0:
            frame_start = idx + MAGIC_LEN
            if len(data) - frame_start > struct.calcsize(HEADER_STRUCT):
                parse_frame(data[frame_start:])

        time.sleep(0.05)


if __name__ == "__main__":
     main()
