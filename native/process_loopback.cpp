// SimpleCast per-process WASAPI loopback helper.
//
// Writes raw stereo, signed 16-bit little-endian PCM to stdout at the requested
// sample rate (44.1 kHz by default).
// The implementation follows Microsoft's ApplicationLoopback sample, but uses
// a synchronous event loop so it can act as a small pipe-based helper.

#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <audioclient.h>
#include <audioclientactivationparams.h>
#include <mmdeviceapi.h>
#include <wrl.h>
#include <fcntl.h>
#include <io.h>

#include <cstdio>
#include <cstdlib>
#include <vector>

using Microsoft::WRL::ComPtr;
using Microsoft::WRL::FtmBase;
using Microsoft::WRL::RuntimeClass;
using Microsoft::WRL::RuntimeClassFlags;
using Microsoft::WRL::ClassicCom;

namespace
{
constexpr DWORD kMinimumProcessLoopbackBuild = 20348;
constexpr DWORD kDefaultSampleRate = 44100;
constexpr WORD kChannels = 2;
constexpr WORD kBitsPerSample = 16;

class ActivationHandler final
    : public RuntimeClass<
          RuntimeClassFlags<ClassicCom>,
          FtmBase,
          IActivateAudioInterfaceCompletionHandler>
{
public:
    ActivationHandler() : completed_(CreateEventW(nullptr, TRUE, FALSE, nullptr))
    {
    }

    ~ActivationHandler()
    {
        if (completed_)
        {
            CloseHandle(completed_);
        }
    }

    STDMETHODIMP ActivateCompleted(
        IActivateAudioInterfaceAsyncOperation* operation) override
    {
        HRESULT activationResult = E_UNEXPECTED;
        ComPtr<IUnknown> audioInterface;
        HRESULT result = operation->GetActivateResult(
            &activationResult,
            &audioInterface);
        if (SUCCEEDED(result))
        {
            result = activationResult;
        }
        if (SUCCEEDED(result))
        {
            result = audioInterface.As(&audioClient_);
        }
        result_ = result;
        SetEvent(completed_);
        return S_OK;
    }

    HRESULT WaitForClient(ComPtr<IAudioClient>& client)
    {
        if (!completed_)
        {
            return HRESULT_FROM_WIN32(GetLastError());
        }
        const DWORD waitResult = WaitForSingleObject(completed_, 15000);
        if (waitResult != WAIT_OBJECT_0)
        {
            return waitResult == WAIT_TIMEOUT
                ? HRESULT_FROM_WIN32(ERROR_TIMEOUT)
                : HRESULT_FROM_WIN32(GetLastError());
        }
        if (SUCCEEDED(result_))
        {
            client = audioClient_;
        }
        return result_;
    }

private:
    HANDLE completed_ = nullptr;
    HRESULT result_ = E_PENDING;
    ComPtr<IAudioClient> audioClient_;
};

DWORD WindowsBuildNumber()
{
    using RtlGetVersionFn = LONG(WINAPI*)(PRTL_OSVERSIONINFOW);
    const HMODULE ntdll = GetModuleHandleW(L"ntdll.dll");
    if (!ntdll)
    {
        return 0;
    }
    const auto rtlGetVersion = reinterpret_cast<RtlGetVersionFn>(
        GetProcAddress(ntdll, "RtlGetVersion"));
    if (!rtlGetVersion)
    {
        return 0;
    }
    RTL_OSVERSIONINFOW version{};
    version.dwOSVersionInfoSize = sizeof(version);
    return rtlGetVersion(&version) == 0 ? version.dwBuildNumber : 0;
}

void PrintError(const wchar_t* context, HRESULT result)
{
    wchar_t* message = nullptr;
    FormatMessageW(
        FORMAT_MESSAGE_FROM_SYSTEM |
            FORMAT_MESSAGE_IGNORE_INSERTS |
            FORMAT_MESSAGE_ALLOCATE_BUFFER,
        nullptr,
        result,
        MAKELANGID(LANG_NEUTRAL, SUBLANG_DEFAULT),
        reinterpret_cast<wchar_t*>(&message),
        0,
        nullptr);
    fwprintf(
        stderr,
        L"%ls failed (0x%08X)%ls%ls\n",
        context,
        static_cast<unsigned int>(result),
        message ? L": " : L"",
        message ? message : L"");
    if (message)
    {
        LocalFree(message);
    }
}

HRESULT WritePacket(
    HANDLE output,
    const BYTE* data,
    UINT32 frames,
    DWORD flags,
    const WAVEFORMATEX& format)
{
    const DWORD byteCount = frames * format.nBlockAlign;
    DWORD written = 0;
    if ((flags & AUDCLNT_BUFFERFLAGS_SILENT) != 0)
    {
        std::vector<BYTE> silence(byteCount, 0);
        if (!WriteFile(output, silence.data(), byteCount, &written, nullptr))
        {
            return HRESULT_FROM_WIN32(GetLastError());
        }
    }
    else if (!WriteFile(output, data, byteCount, &written, nullptr))
    {
        return HRESULT_FROM_WIN32(GetLastError());
    }
    return written == byteCount ? S_OK : E_FAIL;
}
} // namespace

int wmain(int argc, wchar_t* argv[])
{
    if (argc < 2 || argc > 3)
    {
        fwprintf(
            stderr,
            L"Usage: simplecast-process-loopback.exe <process-id> [sample-rate]\n");
        return 2;
    }

    const DWORD processId = wcstoul(argv[1], nullptr, 10);
    if (processId == 0)
    {
        fwprintf(stderr, L"The process ID must be a positive number.\n");
        return 2;
    }
    const DWORD sampleRate = argc == 3
        ? wcstoul(argv[2], nullptr, 10)
        : kDefaultSampleRate;
    if (sampleRate < 8000 || sampleRate > 192000)
    {
        fwprintf(stderr, L"The sample rate is outside the supported range.\n");
        return 2;
    }

    const DWORD build = WindowsBuildNumber();
    if (build != 0 && build < kMinimumProcessLoopbackBuild)
    {
        fwprintf(
            stderr,
            L"Program audio requires Windows build %lu or newer; this computer "
            L"is running build %lu.\n",
            kMinimumProcessLoopbackBuild,
            build);
        return 3;
    }

    const HRESULT comResult = CoInitializeEx(
        nullptr,
        COINIT_MULTITHREADED);
    if (FAILED(comResult) && comResult != RPC_E_CHANGED_MODE)
    {
        PrintError(L"COM initialization", comResult);
        return 4;
    }

    HANDLE processHandle = OpenProcess(SYNCHRONIZE, FALSE, processId);
    if (!processHandle)
    {
        fwprintf(stderr, L"The selected program is no longer running.\n");
        if (SUCCEEDED(comResult))
        {
            CoUninitialize();
        }
        return 5;
    }

    AUDIOCLIENT_ACTIVATION_PARAMS activation{};
    activation.ActivationType = AUDIOCLIENT_ACTIVATION_TYPE_PROCESS_LOOPBACK;
    activation.ProcessLoopbackParams.TargetProcessId = processId;
    activation.ProcessLoopbackParams.ProcessLoopbackMode =
        PROCESS_LOOPBACK_MODE_INCLUDE_TARGET_PROCESS_TREE;

    PROPVARIANT parameters{};
    parameters.vt = VT_BLOB;
    parameters.blob.cbSize = sizeof(activation);
    parameters.blob.pBlobData = reinterpret_cast<BYTE*>(&activation);

    ComPtr<ActivationHandler> handler =
        Microsoft::WRL::Make<ActivationHandler>();
    ComPtr<IActivateAudioInterfaceAsyncOperation> operation;
    HRESULT result = ActivateAudioInterfaceAsync(
        VIRTUAL_AUDIO_DEVICE_PROCESS_LOOPBACK,
        __uuidof(IAudioClient),
        &parameters,
        handler.Get(),
        &operation);
    ComPtr<IAudioClient> audioClient;
    if (SUCCEEDED(result))
    {
        result = handler->WaitForClient(audioClient);
    }
    if (FAILED(result))
    {
        PrintError(L"Process-loopback activation", result);
        CloseHandle(processHandle);
        if (SUCCEEDED(comResult))
        {
            CoUninitialize();
        }
        return 6;
    }

    WAVEFORMATEX format{};
    format.wFormatTag = WAVE_FORMAT_PCM;
    format.nChannels = kChannels;
    format.nSamplesPerSec = sampleRate;
    format.wBitsPerSample = kBitsPerSample;
    format.nBlockAlign =
        format.nChannels * format.wBitsPerSample / 8;
    format.nAvgBytesPerSec =
        format.nSamplesPerSec * format.nBlockAlign;

    const DWORD streamFlags =
        AUDCLNT_STREAMFLAGS_LOOPBACK |
        AUDCLNT_STREAMFLAGS_EVENTCALLBACK |
        AUDCLNT_STREAMFLAGS_AUTOCONVERTPCM |
        AUDCLNT_STREAMFLAGS_SRC_DEFAULT_QUALITY;
    result = audioClient->Initialize(
        AUDCLNT_SHAREMODE_SHARED,
        streamFlags,
        0,
        0,
        &format,
        nullptr);

    HANDLE sampleReady = nullptr;
    ComPtr<IAudioCaptureClient> captureClient;
    if (SUCCEEDED(result))
    {
        sampleReady = CreateEventW(nullptr, FALSE, FALSE, nullptr);
        if (!sampleReady)
        {
            result = HRESULT_FROM_WIN32(GetLastError());
        }
    }
    if (SUCCEEDED(result))
    {
        result = audioClient->SetEventHandle(sampleReady);
    }
    if (SUCCEEDED(result))
    {
        result = audioClient->GetService(IID_PPV_ARGS(&captureClient));
    }
    if (SUCCEEDED(result))
    {
        result = audioClient->Start();
    }
    if (FAILED(result))
    {
        PrintError(L"Process-loopback stream initialization", result);
        if (sampleReady)
        {
            CloseHandle(sampleReady);
        }
        CloseHandle(processHandle);
        if (SUCCEEDED(comResult))
        {
            CoUninitialize();
        }
        return 7;
    }

    fwprintf(stderr, L"READY\n");
    fflush(stderr);
    _setmode(_fileno(stdout), _O_BINARY);
    HANDLE output = GetStdHandle(STD_OUTPUT_HANDLE);
    HANDLE waitHandles[] = {sampleReady, processHandle};
    bool running = true;
    while (running)
    {
        const DWORD waitResult = WaitForMultipleObjects(
            2,
            waitHandles,
            FALSE,
            INFINITE);
        if (waitResult == WAIT_OBJECT_0 + 1)
        {
            fwprintf(stderr, L"The selected program closed.\n");
            break;
        }
        if (waitResult != WAIT_OBJECT_0)
        {
            PrintError(
                L"Waiting for program audio",
                HRESULT_FROM_WIN32(GetLastError()));
            result = E_FAIL;
            break;
        }

        UINT32 packetFrames = 0;
        while (SUCCEEDED(
                   result = captureClient->GetNextPacketSize(&packetFrames)) &&
               packetFrames > 0)
        {
            BYTE* data = nullptr;
            DWORD flags = 0;
            UINT64 devicePosition = 0;
            UINT64 performancePosition = 0;
            result = captureClient->GetBuffer(
                &data,
                &packetFrames,
                &flags,
                &devicePosition,
                &performancePosition);
            if (FAILED(result))
            {
                running = false;
                break;
            }
            result = WritePacket(
                output,
                data,
                packetFrames,
                flags,
                format);
            const HRESULT releaseResult =
                captureClient->ReleaseBuffer(packetFrames);
            if (FAILED(result) || FAILED(releaseResult))
            {
                if (HRESULT_CODE(result) != ERROR_BROKEN_PIPE)
                {
                    PrintError(
                        L"Writing captured program audio",
                        FAILED(result) ? result : releaseResult);
                }
                running = false;
                break;
            }
        }
        if (FAILED(result))
        {
            break;
        }
    }

    audioClient->Stop();
    CloseHandle(sampleReady);
    CloseHandle(processHandle);
    if (SUCCEEDED(comResult))
    {
        CoUninitialize();
    }
    return FAILED(result) && HRESULT_CODE(result) != ERROR_BROKEN_PIPE ? 8 : 0;
}
