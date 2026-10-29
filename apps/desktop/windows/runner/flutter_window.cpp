#include "flutter_window.h"

#include <optional>
#include <vector>
#include <shobjidl.h>
#include <shlobj.h>
#include <shellapi.h>

#include "flutter/generated_plugin_registrant.h"
#include "utils.h"

FlutterWindow::FlutterWindow(const flutter::DartProject& project)
    : project_(project) {}

FlutterWindow::~FlutterWindow() {}

bool FlutterWindow::OnCreate() {
  if (!Win32Window::OnCreate()) {
    return false;
  }

  RECT frame = GetClientArea();

  // The size here must match the window dimensions to avoid unnecessary surface
  // creation / destruction in the startup path.
  flutter_controller_ = std::make_unique<flutter::FlutterViewController>(
      frame.right - frame.left, frame.bottom - frame.top, project_);
  // Ensure that basic setup of the controller was successful.
  if (!flutter_controller_->engine() || !flutter_controller_->view()) {
    return false;
  }
  RegisterPlugins(flutter_controller_->engine());
  desktop_channel_ = std::make_unique<flutter::MethodChannel<flutter::EncodableValue>>(
      flutter_controller_->engine()->messenger(), "study/desktop",
      &flutter::StandardMethodCodec::GetInstance());
  desktop_channel_->SetMethodCallHandler([this](const auto& call, auto result) {
    if (call.method_name() == "storageRoot" || call.method_name() == "settingsRoot") {
      HANDLE token = nullptr;
      if (!OpenProcessToken(GetCurrentProcess(), TOKEN_QUERY, &token)) {
        result->Error("storage", "Cannot read process integrity");
        return;
      }
      DWORD bytes = 0;
      GetTokenInformation(token, TokenIntegrityLevel, nullptr, 0, &bytes);
      std::vector<BYTE> buffer(bytes);
      const bool queried = bytes && GetTokenInformation(
          token, TokenIntegrityLevel, buffer.data(), bytes, &bytes);
      CloseHandle(token);
      if (!queried) {
        result->Error("storage", "Cannot read process integrity");
        return;
      }
      const auto label = reinterpret_cast<TOKEN_MANDATORY_LABEL*>(buffer.data());
      const DWORD integrity = *GetSidSubAuthority(
          label->Label.Sid, *GetSidSubAuthorityCount(label->Label.Sid) - 1);
      PWSTR path = nullptr;
      HRESULT hr = SHGetKnownFolderPath(
          call.method_name() == "settingsRoot" || integrity < SECURITY_MANDATORY_MEDIUM_RID
              ? FOLDERID_LocalAppDataLow : FOLDERID_LocalAppData,
          KF_FLAG_DEFAULT, nullptr, &path);
      if (FAILED(hr)) {
        result->Error("storage", "Cannot locate user application data");
        return;
      }
      const std::string root = Utf8FromUtf16(path) + "/StudyWorkbench";
      CoTaskMemFree(path);
      result->Success(flutter::EncodableValue(root));
      return;
    }
    const bool choose_file = call.method_name() == "chooseImportFile";
    const bool save_file = call.method_name() == "chooseExportFile";
    const bool resource_folder = call.method_name() == "chooseResourceDirectory";
    if (call.method_name() != "chooseDirectory" && !resource_folder && !choose_file && !save_file) {
      result->NotImplemented();
      return;
    }
    IFileDialog* dialog = nullptr;
    HRESULT hr = CoCreateInstance(save_file ? CLSID_FileSaveDialog : CLSID_FileOpenDialog,
                                 nullptr, CLSCTX_INPROC_SERVER,
                                 IID_PPV_ARGS(&dialog));
    if (FAILED(hr)) {
      result->Error("folder", "Cannot create folder picker");
      return;
    }
    DWORD options = 0;
    dialog->GetOptions(&options);
    dialog->SetOptions(options | FOS_FORCEFILESYSTEM |
                       (save_file ? FOS_OVERWRITEPROMPT :
                        choose_file ? FOS_FILEMUSTEXIST : FOS_PICKFOLDERS));
    dialog->SetTitle(save_file ? L"导出当前工作空间资料" :
                     choose_file ? L"选择要导入的学习资料" :
                     resource_folder ? L"选择要复制导入的资源文件夹（原目录保留）" : L"选择 StudyWorkbench 数据文件夹");
    if (save_file) {
      dialog->SetDefaultExtension(L"zip");
      dialog->SetFileName(L"StudyWorkbench资料.zip");
    }
    hr = dialog->Show(GetHandle());
    std::string selected;
    if (SUCCEEDED(hr)) {
      IShellItem* item = nullptr;
      if (SUCCEEDED(dialog->GetResult(&item))) {
        PWSTR path = nullptr;
        if (SUCCEEDED(item->GetDisplayName(SIGDN_FILESYSPATH, &path))) {
          int size = WideCharToMultiByte(CP_UTF8, 0, path, -1, nullptr, 0, nullptr, nullptr);
          selected.resize(size);
          WideCharToMultiByte(CP_UTF8, 0, path, -1, selected.data(), size, nullptr, nullptr);
          selected.pop_back();
          CoTaskMemFree(path);
        }
        item->Release();
      }
    }
    dialog->Release();
    if (hr == HRESULT_FROM_WIN32(ERROR_CANCELLED)) result->Success();
    else if (FAILED(hr) || selected.empty()) result->Error("folder", "Cannot select folder");
    else result->Success(flutter::EncodableValue(selected));
  });
  SetChildContent(flutter_controller_->view()->GetNativeWindow());

  flutter_controller_->engine()->SetNextFrameCallback([&]() {
    this->Show();
  });

  // Flutter can complete the first frame before the "show window" callback is
  // registered. The following call ensures a frame is pending to ensure the
  // window is shown. It is a no-op if the first frame hasn't completed yet.
  flutter_controller_->ForceRedraw();

  return true;
}

void FlutterWindow::OnDestroy() {
  desktop_channel_.reset();
  if (flutter_controller_) {
    flutter_controller_ = nullptr;
  }

  Win32Window::OnDestroy();
}

LRESULT
FlutterWindow::MessageHandler(HWND hwnd, UINT const message,
                              WPARAM const wparam,
                              LPARAM const lparam) noexcept {
  // Give Flutter, including plugins, an opportunity to handle window messages.
  if (flutter_controller_) {
    std::optional<LRESULT> result =
        flutter_controller_->HandleTopLevelWindowProc(hwnd, message, wparam,
                                                      lparam);
    if (result) {
      return *result;
    }
  }

  switch (message) {
    case WM_FONTCHANGE:
      flutter_controller_->engine()->ReloadSystemFonts();
      break;
  }

  return Win32Window::MessageHandler(hwnd, message, wparam, lparam);
}
