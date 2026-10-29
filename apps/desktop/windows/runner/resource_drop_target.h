#ifndef RUNNER_RESOURCE_DROP_TARGET_H_
#define RUNNER_RESOURCE_DROP_TARGET_H_

#include <windows.h>
#include <oleidl.h>
#include <flutter/method_channel.h>

class ResourceDropTarget : public IDropTarget {
 public:
  ResourceDropTarget(HWND window, flutter::MethodChannel<flutter::EncodableValue>* channel)
      : window_(window), channel_(channel) {}
  RECT bounds{};
  bool enabled = false;
  HRESULT STDMETHODCALLTYPE QueryInterface(REFIID iid, void** object) override;
  ULONG STDMETHODCALLTYPE AddRef() override;
  ULONG STDMETHODCALLTYPE Release() override;
  HRESULT STDMETHODCALLTYPE DragEnter(IDataObject*, DWORD, POINTL, DWORD*) override;
  HRESULT STDMETHODCALLTYPE DragOver(DWORD, POINTL, DWORD*) override;
  HRESULT STDMETHODCALLTYPE DragLeave() override;
  HRESULT STDMETHODCALLTYPE Drop(IDataObject*, DWORD, POINTL, DWORD*) override;

 private:
  void Hover(bool active);
  bool Inside(POINTL point);
  ULONG refs_ = 1;
  HWND window_;
  flutter::MethodChannel<flutter::EncodableValue>* channel_;
  bool files_ = false, hovering_ = false;
};
#endif
