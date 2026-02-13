#include <windows.h>
#include <stdio.h>
#include <stdint.h>
#include <string.h>
#include <ctype.h>

#define COM_PORT "\\\\.\\COM7"    // Use correct COM port (e.g., "\\\\.\\COM3")
#define BAUD_RATE 921600
#define BUFFER_SIZE 4096
#define MAGIC_WORD_LEN 8
#define DETECTED_OBJ_TLV_TYPE 6

uint8_t MAGIC_WORD[MAGIC_WORD_LEN] = { 0x02, 0x01, 0x04, 0x03, 0x06, 0x05, 0x08, 0x07 };

#pragma pack(push, 1)
typedef struct {
    uint32_t version;
    uint32_t totalPacketLen;
    uint32_t platform;                                       
    uint32_t frameNumber;
    uint32_t timeCpuCycles;
    uint32_t numDetectedObj;
    uint32_t numTLVs;
    uint32_t subFrameNumber;
} MmwDemo_output_message_header;

typedef struct {
    uint32_t type;
    uint32_t length;
} tlvHeader;
 
typedef struct {
    float x;
    float y;
    float z;
    float velocity;                   
} detectedObj;
#pragma pack(pop)

HANDLE open_serial_port(const char* portName) {
    printf("Opening %s...\n", portName);

    HANDLE hSerial = CreateFileA(
        portName, GENERIC_READ, 0, NULL, OPEN_EXISTING, 0, NULL);

    if (hSerial == INVALID_HANDLE_VALUE) {
        printf("ERROR: Cannot open %s (err=%lu)\n", portName, (unsigned long)GetLastError());
        return INVALID_HANDLE_VALUE;
    }

    DCB dcbSerialParams = { 0 };
    dcbSerialParams.DCBlength = sizeof(dcbSerialParams);

    if (!GetCommState(hSerial, &dcbSerialParams)) {
        printf("Failed to get COM state (err=%lu)\n", (unsigned long)GetLastError());
        CloseHandle(hSerial);
        return INVALID_HANDLE_VALUE;
    }

    dcbSerialParams.BaudRate = BAUD_RATE;
    dcbSerialParams.ByteSize = 8;
    dcbSerialParams.StopBits = ONESTOPBIT;
    dcbSerialParams.Parity   = NOPARITY;
    dcbSerialParams.fDtrControl = DTR_CONTROL_DISABLE;

    if (!SetCommState(hSerial, &dcbSerialParams)) {
        printf("Failed to set COM state (err=%lu)\n", (unsigned long)GetLastError());
        CloseHandle(hSerial);
        return INVALID_HANDLE_VALUE;
    }

    COMMTIMEOUTS timeouts = { 0 };
    timeouts.ReadIntervalTimeout = 50;
    timeouts.ReadTotalTimeoutConstant = 50;
    timeouts.ReadTotalTimeoutMultiplier = 10;

    if (!SetCommTimeouts(hSerial, &timeouts)) {
        printf("Failed to set timeouts (err=%lu)\n", (unsigned long)GetLastError());
        CloseHandle(hSerial);
        return INVALID_HANDLE_VALUE;
    }

    return hSerial;
}

int find_magic_word(uint8_t* buffer, int len) {
    for (int i = 0; i < len - MAGIC_WORD_LEN; ++i) {
        if (memcmp(buffer + i, MAGIC_WORD, MAGIC_WORD_LEN) == 0) {
            return i;
        }
    }
    return -1;
}

void parse_tlvs(uint8_t* data, uint32_t numTLVs, uint32_t numDetectedObj) {
    for (uint32_t i = 0; i < numTLVs; ++i) {
        tlvHeader tlv;
        memcpy(&tlv, data, sizeof(tlvHeader));
        data += sizeof(tlvHeader);

        if (tlv.type == DETECTED_OBJ_TLV_TYPE) {
            printf("Detected Objects: %u\n", numDetectedObj);
            for (uint32_t j = 0; j < numDetectedObj; ++j) {
                detectedObj obj;
                memcpy(&obj, data + j * sizeof(detectedObj), sizeof(detectedObj));
                printf("  Object %u: X=%.2f, Y=%.2f, Z=%.2f, V=%.2f\n",
                    j + 1, obj.x, obj.y, obj.z, obj.velocity);
            }
        }

        data += tlv.length - sizeof(tlvHeader);
    }
}

void parse_frame(uint8_t* frame) { 
    MmwDemo_output_message_header header;
    memcpy(&header, frame, sizeof(header));

    printf("\n=== Frame %u ===\n", header.frameNumber);
    parse_tlvs(frame + sizeof(header), header.numTLVs, header.numDetectedObj);
}

void print_raw_data(uint8_t* buffer, DWORD len) {
    for (DWORD i = 0; i < len; i += 16) {
        printf("%04lx  ", i);
        for (DWORD j = 0; j < 16; ++j) {
            if (i + j < len)
                printf("%02X ", buffer[i + j]);
            else
                printf("   ");
        }
        printf(" ");
        for (DWORD j = 0; j < 16; ++j) {
            if (i + j < len)
                printf("%c", isprint(buffer[i + j]) ? buffer[i + j] : '.');
        }
        printf("\n");
    }
}

int main() {
    HANDLE serialHandle = open_serial_port(COM_PORT);
    if (serialHandle == INVALID_HANDLE_VALUE) return 1;

    uint8_t buffer[BUFFER_SIZE];
    DWORD bytesRead;

    while (1) {
        if (!ReadFile(serialHandle, buffer, BUFFER_SIZE, &bytesRead, NULL)) {
            printf("Error reading from serial port (err=%lu)\n", (unsigned long)GetLastError());
            break;
        }

        if (bytesRead == 0) continue;

        printf("\n--- Raw Data (%lu bytes) ---\n", (unsigned long)bytesRead);
        print_raw_data(buffer, bytesRead);                     

        int index = find_magic_word(buffer, bytesRead);
        if (index >= 0 && (bytesRead - index) > sizeof(MmwDemo_output_message_header)) {
            uint8_t* frameStart = buffer + index + MAGIC_WORD_LEN;
            parse_frame(frameStart);
        }

        Sleep(50); // 50 ms delay
    }

    CloseHandle(serialHandle);
    return 0;
}