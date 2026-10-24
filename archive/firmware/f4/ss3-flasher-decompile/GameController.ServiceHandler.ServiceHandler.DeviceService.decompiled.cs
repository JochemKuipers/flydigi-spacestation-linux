using System;
using System.Management;
using System.Threading.Tasks;
using GameController.ServiceHandler.Config;
using GameController.ServiceHandler.DataManager;
using GameController.ServiceHandler.Service;
using GameController.ServiceHandler.Service.Protocol;
using LibCommon.Utils;

namespace GameController.ServiceHandler.ServiceHandler;

public class DeviceService
{
	private static USB USBWatcher;

	public static Task taskRemove;

	public static Task taskAdd;

	public static void Start()
	{
		HandleUsbManager();
		FoundDevices();
	}

	private static void HandleUsbManager()
	{
		//IL_0013: Unknown result type (might be due to invalid IL or missing references)
		//IL_001f: Unknown result type (might be due to invalid IL or missing references)
		//IL_0031: Expected Obj, but got Unknown
		//IL_0031: Expected Obj, but got Unknown
		if (USBWatcher == null)
		{
			new USB().AddUSBEventWatcher(USBEventHandler, USBRemoveEventHandler, new TimeSpan(0, 0, 1));
		}
	}

	private static async void USBEventHandler(object sender, EventArrivedEventArgs e)
	{
		if (taskAdd != null && !taskAdd.IsCompleted)
		{
			return;
		}
		bool isFlydigiDevice = USB.IsFlydigiDevice(e);
		if (USB.IsFlydigiBLEDevice(e))
		{
			BLEDeviceService.ConnectedCB();
		}
		FLog.d("FDGTransData IsAllowCheck 1:" + FDGTransData.IsAllowCheck);
		if (!FDGTransData.IsAllowCheck)
		{
			return;
		}
		FLog.d("FDGTransData IsAllowCheck 2:" + FDGTransData.IsAllowCheck);
		taskAdd = Task.Run(async () =>
		{
			_ = (ManagementBaseObject)e.NewEvent.Properties["TargetInstance"].Value;
			FLog.d("【USB1】Add device,Start to refresh devicelist");
			FLog.d("【USB2】Add device,Start to refresh devicelist");
			if (isFlydigiDevice)
			{
				FoundDevices(status: true);
			}
		});
	}

	private static void USBRemoveEventHandler(object sender, EventArrivedEventArgs e)
	{
		if (taskRemove != null && !taskRemove.IsCompleted)
		{
			return;
		}
		FLog.d("FDGTransData IsAllowCheck 1:" + FDGTransData.IsAllowCheck);
		bool isFlydigiDevice = USB.IsFlydigiDevice(e);
		if (USB.IsFlydigiBLEDeviceRemove(e))
		{
			BLEDeviceService.UnConnectedCB();
		}
		if (!FDGTransData.IsAllowCheck)
		{
			return;
		}
		FLog.d("FDGTransData IsAllowCheck 2:" + FDGTransData.IsAllowCheck);
		taskRemove = Task.Run(async () =>
		{
			UsbDataManager.IsFMUpgrade = false;
			_ = (ManagementBaseObject)e.NewEvent.Properties["TargetInstance"].Value;
			FLog.d("【USB】Remove Device,Start to refresh devicelist");
			if (isFlydigiDevice)
			{
				FoundDevices();
			}
		});
	}

	public static void Stop()
	{
		if (USBWatcher != null)
		{
			USBWatcher.RemoveUSBEventWatcher();
		}
	}

	public static int FoundDevices(bool status = false)
	{
		return DriveDetector.OpenDevice(status).Count;
	}

	public static void FoundBLEDevices()
	{
		if (FDGDevice.HasFlydigiBLEDevice())
		{
			BLEDeviceService.ConnectedCB();
		}
	}
}
