#include "resource_drop_target.h"
#include <shellapi.h>
#include <vector>
#include <flutter/standard_method_codec.h>
#include "utils.h"

HRESULT ResourceDropTarget::QueryInterface(REFIID iid, void** object) {
  if (!object) return E_POINTER;
  *object = nullptr;
  if (iid != IID_IUnknown && iid != IID_IDropTarget) return E_NOINTERFACE;
  *object = static_cast<IDropTarget*>(this);
  AddRef();
  return S_OK;
}
ULONG ResourceDropTarget::AddRef() { return ++refs_; }
ULONG ResourceDropTarget::Release() {
  const ULONG remaining = --refs_;
  if (!remaining) delete this;
  return remaining;
}
bool ResourceDropTarget::Inside(POINTL point) {
  POINT client{point.x, point.y};
  ScreenToClient(window_, &client);
  return enabled && files_ && PtInRect(&bounds, client);
}
void ResourceDropTarget::Hover(bool active) {
  if (hovering_ == active) return;
  hovering_ = active;
  channel_->InvokeMethod("resourceDrag", std::make_unique<flutter::EncodableValue>(active));
}
HRESULT ResourceDropTarget::DragEnter(IDataObject* data, DWORD, POINTL point, DWORD* effect) {
  FORMATETC format{CF_HDROP, nullptr, DVASPECT_CONTENT, -1, TYMED_HGLOBAL};
  files_ = SUCCEEDED(data->QueryGetData(&format));
  return DragOver(0, point, effect);
}
HRESULT ResourceDropTarget::DragOver(DWORD, POINTL point, DWORD* effect) {
  const bool active = Inside(point) && (*effect & DROPEFFECT_COPY);
  *effect = active ? DROPEFFECT_COPY : DROPEFFECT_NONE;
  Hover(active);
  return S_OK;
}
HRESULT ResourceDropTarget::DragLeave() {
  files_ = false;
  Hover(false);
  return S_OK;
}
HRESULT ResourceDropTarget::Drop(IDataObject* data, DWORD, POINTL point, DWORD* effect) {
  const bool accept = Inside(point) && (*effect & DROPEFFECT_COPY);
  *effect = DROPEFFECT_NONE;
  if (accept) {
    FORMATETC format{CF_HDROP, nullptr, DVASPECT_CONTENT, -1, TYMED_HGLOBAL};
    STGMEDIUM storage{};
    if (SUCCEEDED(data->GetData(&format, &storage))) {
      const HDROP drop = static_cast<HDROP>(storage.hGlobal);
      const UINT count = DragQueryFileW(drop, 0xFFFFFFFF, nullptr, 0);
      flutter::EncodableList paths;
      if (count > 1000) {
        channel_->InvokeMethod("resourceDropError", std::make_unique<flutter::EncodableValue>("一次最多添加1000项"));
      } else {
        for (UINT i = 0; i < count; ++i) {
          const UINT length = DragQueryFileW(drop, i, nullptr, 0);
          std::vector<wchar_t> path(length + 1);
          if (DragQueryFileW(drop, i, path.data(), length + 1))
            paths.emplace_back(Utf8FromUtf16(path.data()));
        }
        channel_->InvokeMethod("resourceDrop", std::make_unique<flutter::EncodableValue>(paths));
        *effect = DROPEFFECT_COPY;
      }
      ReleaseStgMedium(&storage);
    }
  }
  DragLeave();
  return S_OK;
}
