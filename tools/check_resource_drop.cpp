// Native COM boundary check, independent of Explorer mouse automation.
#undef NDEBUG
#include <cassert>
#include <algorithm>
#include <cstring>
#include <windows.h>
#include <shlobj.h>
#include <shellapi.h>
#include <flutter/standard_method_codec.h>
#include "../apps/desktop/windows/runner/resource_drop_target.h"

class Messenger : public flutter::BinaryMessenger {
 public:
  mutable std::vector<std::string> methods;
  mutable flutter::EncodableList paths;
  void Send(const std::string&, const uint8_t* bytes, size_t length,
            flutter::BinaryReply = nullptr) const override {
    const auto call = flutter::StandardMethodCodec::GetInstance().DecodeMethodCall(bytes, length);
    methods.push_back(call->method_name());
    if (call->method_name() == "resourceDrop") paths = std::get<flutter::EncodableList>(*call->arguments());
  }
  void SetMessageHandler(const std::string&, flutter::BinaryMessageHandler) override {}
};

class Files : public IDataObject {
 public:
  bool valid = true;
  std::vector<std::wstring> paths{L"D:\\中文.md", L"D:\\video.webm"};
  HRESULT STDMETHODCALLTYPE QueryInterface(REFIID iid, void** object) override {
    *object = nullptr;
    if (iid != IID_IUnknown && iid != IID_IDataObject) return E_NOINTERFACE;
    *object = static_cast<IDataObject*>(this);
    AddRef(); return S_OK;
  }
  ULONG STDMETHODCALLTYPE AddRef() override { return ++refs; }
  ULONG STDMETHODCALLTYPE Release() override { return --refs; }
  HRESULT STDMETHODCALLTYPE QueryGetData(FORMATETC* format) override {
    return valid && format->cfFormat == CF_HDROP && format->tymed == TYMED_HGLOBAL ? S_OK : DV_E_FORMATETC;
  }
  HRESULT STDMETHODCALLTYPE GetData(FORMATETC* format, STGMEDIUM* storage) override {
    if (FAILED(QueryGetData(format))) return DV_E_FORMATETC;
    size_t chars = 1;
    for (const auto& path : paths) chars += path.size() + 1;
    storage->tymed = TYMED_HGLOBAL;
    storage->pUnkForRelease = nullptr;
    storage->hGlobal = GlobalAlloc(GHND, sizeof(DROPFILES) + chars * sizeof(wchar_t));
    assert(storage->hGlobal);
    auto* drop = static_cast<DROPFILES*>(GlobalLock(storage->hGlobal));
    drop->pFiles = sizeof(DROPFILES); drop->fWide = TRUE;
    auto* cursor = reinterpret_cast<wchar_t*>(reinterpret_cast<BYTE*>(drop) + sizeof(DROPFILES));
    for (const auto& path : paths) {
      memcpy(cursor, path.c_str(), (path.size() + 1) * sizeof(wchar_t));
      cursor += path.size() + 1;
    }
    GlobalUnlock(storage->hGlobal);
    return S_OK;
  }
  HRESULT STDMETHODCALLTYPE GetDataHere(FORMATETC*, STGMEDIUM*) override { return E_NOTIMPL; }
  HRESULT STDMETHODCALLTYPE GetCanonicalFormatEtc(FORMATETC*, FORMATETC*) override { return E_NOTIMPL; }
  HRESULT STDMETHODCALLTYPE SetData(FORMATETC*, STGMEDIUM*, BOOL) override { return E_NOTIMPL; }
  HRESULT STDMETHODCALLTYPE EnumFormatEtc(DWORD, IEnumFORMATETC**) override { return E_NOTIMPL; }
  HRESULT STDMETHODCALLTYPE DAdvise(FORMATETC*, DWORD, IAdviseSink*, DWORD*) override { return OLE_E_ADVISENOTSUPPORTED; }
  HRESULT STDMETHODCALLTYPE DUnadvise(DWORD) override { return OLE_E_ADVISENOTSUPPORTED; }
  HRESULT STDMETHODCALLTYPE EnumDAdvise(IEnumSTATDATA**) override { return OLE_E_ADVISENOTSUPPORTED; }
 private:
  ULONG refs = 1;
};

int main() {
  assert(SUCCEEDED(OleInitialize(nullptr)));
  const HWND window = CreateWindowExW(0, L"STATIC", L"drop-check", WS_POPUP, 0, 0, 400, 400,
                                    nullptr, nullptr, GetModuleHandle(nullptr), nullptr);
  assert(window);
  Messenger messenger;
  flutter::MethodChannel<flutter::EncodableValue> channel(&messenger, "study/desktop", &flutter::StandardMethodCodec::GetInstance());
  auto* target = new ResourceDropTarget(window, &channel);
  assert(SUCCEEDED(RegisterDragDrop(window, target)));
  target->bounds = {20, 20, 300, 300};
  Files files;
  DWORD effect = DROPEFFECT_COPY;
  target->DragEnter(&files, 0, {50, 50}, &effect);
  assert(effect == DROPEFFECT_NONE && messenger.methods.empty());
  target->enabled = true;
  effect = DROPEFFECT_COPY;
  target->DragOver(0, {50, 50}, &effect);
  assert(effect == DROPEFFECT_COPY && messenger.methods.back() == "resourceDrag");
  effect = DROPEFFECT_COPY;
  target->DragOver(0, {350, 350}, &effect);
  assert(effect == DROPEFFECT_NONE);
  effect = DROPEFFECT_COPY;
  target->Drop(&files, 0, {350, 350}, &effect);
  assert(effect == DROPEFFECT_NONE && messenger.paths.empty());
  effect = DROPEFFECT_COPY;
  target->DragEnter(&files, 0, {50, 50}, &effect);
  target->Drop(&files, 0, {50, 50}, &effect);
  assert(effect == DROPEFFECT_COPY && messenger.paths.size() == 2);
  assert(std::get<std::string>(messenger.paths[0]) == "D:\\中文.md");
  files.paths.resize(1);
  effect = DROPEFFECT_COPY;
  target->DragEnter(&files, 0, {50, 50}, &effect);
  target->Drop(&files, 0, {50, 50}, &effect);
  assert(messenger.paths.size() == 1);
  files.paths.resize(1001, L"D:\\x.txt");
  effect = DROPEFFECT_COPY;
  target->DragEnter(&files, 0, {50, 50}, &effect);
  target->Drop(&files, 0, {50, 50}, &effect);
  assert(effect == DROPEFFECT_NONE && std::find(messenger.methods.begin(), messenger.methods.end(),
                                              "resourceDropError") != messenger.methods.end());
  files.valid = false;
  effect = DROPEFFECT_COPY;
  target->DragEnter(&files, 0, {50, 50}, &effect);
  assert(effect == DROPEFFECT_NONE);
  target->DragLeave();
  assert(SUCCEEDED(RevokeDragDrop(window)));
  target->Release();
  DestroyWindow(window);
  OleUninitialize();
  return 0;
}
