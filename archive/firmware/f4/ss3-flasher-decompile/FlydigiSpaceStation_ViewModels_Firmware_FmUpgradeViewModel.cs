using System;
using System.Collections.ObjectModel;
using System.Linq;
using System.Runtime.CompilerServices;
using System.Threading;
using System.Threading.Tasks;
using FlydigiSpaceStation.Assets.Localization.Language;
using FlydigiSpaceStation.Common;
using FlydigiSpaceStation.Common.Services.Api;
using FlydigiSpaceStation.Common.Utils;
using LibCommon.Model;
using LibCommon.Services.Driver;
using LibCommon.Services.FirmwareDriver.WchIsp;
using LibCommon.Utils;
using Prism.Commands;
using Prism.Events;
using Prism.Mvvm;
using Prism.Regions;
using Prism.Services.Dialogs;

namespace FlydigiSpaceStation.ViewModels.Firmware;

internal class FmUpgradeViewModel : BindableBase, IConfigureService, IDialogAware
{
	private readonly IRegionManager regionManager;

	private IRegionNavigationJournal journal;

	public static string currentLanguage;

	public static FDGDeviceFirmware gamepadModel;

	private string _appTitle;

	private string _mClearDataFlashText;

	private ObservableCollection<FDGDeviceFirmware> _gamepadInfo;

	private ObservableCollection<FirmwareUpgreadeInfo> _upgreadeInfo;

	private ObservableCollection<ProductSnModel> productSn;

	private FDGDeviceFirmware _selectGamepadInfo;

	private ProductSnModel _selectProductSn;

	private string _gamepadConnectStatus;

	private string _gamepadEndStatus;

	private string _upgradeHelpTip;

	private string _upgradeTitle;

	private string _upgradeContent;

	private int _downloadProgress;

	private int _selectIndex;

	private bool _showUnConnectButton = true;

	private bool _showConnectButton = false;

	private bool _showDownloadEndButton = false;

	private bool _showClearDataFlashBox = false;

	private bool _showProductSnBox = false;

	private WchIspManager _wchIspManager;

	private bool _isIndicatorVisible;

	private bool _isProductSnVisible;

	private bool isClearDataFlash;

	private string _currentLanguage;

	private readonly IEventAggregator _eventAggregator;

	public bool IsDownloadSuccess = false;

	private DelegateCommand _RepairDriverCmd;

	private DelegateCommand _closeWindowCmd;

	private bool _dialogResult;

	private bool _IsShowTipInfo;

	private string _TipInfo;

	public bool ShowProductSnBox
	{
		get
		{
			return _showProductSnBox;
		}
		set
		{
			if (_showProductSnBox != value)
			{
				_showProductSnBox = value;
				RaisePropertyChanged("ShowProductSnBox");
			}
		}
	}

	public DelegateCommand UploadFileCommand
	{
		get;
		[CompilerGenerated]
		private set
		{
			if (!object.Equals(field, value))
			{
				field = value;
				OnPropertyChanged(<>PropertyChangedEventArgs.UploadFileCommand);
			}
		}
	}

	public DelegateCommand GoConnectSuccessCommand
	{
		get;
		[CompilerGenerated]
		private set
		{
			if (!object.Equals(field, value))
			{
				field = value;
				OnPropertyChanged(<>PropertyChangedEventArgs.GoConnectSuccessCommand);
			}
		}
	}

	public DelegateCommand GoFirstCommand
	{
		get;
		[CompilerGenerated]
		private set
		{
			if (!object.Equals(field, value))
			{
				field = value;
				OnPropertyChanged(<>PropertyChangedEventArgs.GoFirstCommand);
			}
		}
	}

	public DelegateCommand RepairDriverCmd => _RepairDriverCmd ?? (_RepairDriverCmd = new DelegateCommand(ExecuteRepairDriverCmd));

	public bool ShowDownloadEndButton
	{
		get
		{
			return _showDownloadEndButton;
		}
		set
		{
			if (_showDownloadEndButton != value)
			{
				_showDownloadEndButton = value;
				RaisePropertyChanged("ShowDownloadEndButton");
			}
		}
	}

	public bool ShowClearDataFlashBox
	{
		get
		{
			return _showClearDataFlashBox;
		}
		set
		{
			if (_showClearDataFlashBox != value)
			{
				_showClearDataFlashBox = value;
				RaisePropertyChanged("ShowClearDataFlashBox");
			}
		}
	}

	public bool IsIndicatorVisible
	{
		get
		{
			return _isIndicatorVisible;
		}
		set
		{
			if (_isIndicatorVisible != value)
			{
				_isIndicatorVisible = value;
				RaisePropertyChanged("IsIndicatorVisible");
			}
		}
	}

	public bool IsProductSnVisible
	{
		get
		{
			return _isProductSnVisible;
		}
		set
		{
			if (_isProductSnVisible != value)
			{
				_isProductSnVisible = value;
				RaisePropertyChanged("IsProductSnVisible");
			}
		}
	}

	public bool ShowUnConnectButton
	{
		get
		{
			return _showUnConnectButton;
		}
		set
		{
			if (_showUnConnectButton != value)
			{
				_showUnConnectButton = value;
				RaisePropertyChanged("ShowUnConnectButton");
			}
		}
	}

	public bool ShowConnectButton
	{
		get
		{
			return _showConnectButton;
		}
		set
		{
			if (_showConnectButton != value)
			{
				_showConnectButton = value;
				RaisePropertyChanged("ShowConnectButton");
			}
		}
	}

	public int DownloadProgress
	{
		get
		{
			return _downloadProgress;
		}
		set
		{
			if (_downloadProgress != value)
			{
				_downloadProgress = value;
				RaisePropertyChanged("DownloadProgress");
			}
		}
	}

	public string GamepadConnectStatus
	{
		get
		{
			return _gamepadConnectStatus;
		}
		set
		{
			if (!string.Equals(_gamepadConnectStatus, value, StringComparison.Ordinal))
			{
				_gamepadConnectStatus = value;
				RaisePropertyChanged("GamepadConnectStatus");
			}
		}
	}

	public string GamepadEndStatus
	{
		get
		{
			return _gamepadEndStatus;
		}
		set
		{
			if (!string.Equals(_gamepadEndStatus, value, StringComparison.Ordinal))
			{
				_gamepadEndStatus = value;
				RaisePropertyChanged("GamepadEndStatus");
			}
		}
	}

	public string UpgradeHelpTip
	{
		get
		{
			return _upgradeHelpTip;
		}
		set
		{
			if (!string.Equals(_upgradeHelpTip, value, StringComparison.Ordinal))
			{
				_upgradeHelpTip = value;
				RaisePropertyChanged("UpgradeHelpTip");
			}
		}
	}

	public string UpgradeTitle
	{
		get
		{
			return _upgradeTitle;
		}
		set
		{
			if (!string.Equals(_upgradeTitle, value, StringComparison.Ordinal))
			{
				_upgradeTitle = value;
				RaisePropertyChanged("UpgradeTitle");
			}
		}
	}

	public string UpgradeContent
	{
		get
		{
			return _upgradeContent;
		}
		set
		{
			if (!string.Equals(_upgradeContent, value, StringComparison.Ordinal))
			{
				_upgradeContent = value;
				RaisePropertyChanged("UpgradeContent");
			}
		}
	}

	public int SelectIndex
	{
		get
		{
			return _selectIndex;
		}
		set
		{
			if (_selectIndex != value)
			{
				_selectIndex = value;
				RaisePropertyChanged("SelectIndex");
			}
		}
	}

	public ProductSnModel SelectProductSn
	{
		get
		{
			return _selectProductSn;
		}
		set
		{
			if (!object.Equals(_selectProductSn, value))
			{
				_selectProductSn = value;
				RaisePropertyChanged("SelectProductSn");
				if (SelectProductSn.ShowName == "NR")
				{
					_selectGamepadInfo.FirmName = "f1wch";
				}
				else if (SelectProductSn.ShowName == "NL")
				{
					_selectGamepadInfo.FirmName = "F1P";
				}
				new Thread(() =>
				{
					CheckFirmwareVersion();
				}).Start();
			}
		}
	}

	public FDGDeviceFirmware SelectGamepadInfo
	{
		get
		{
			return _selectGamepadInfo;
		}
		set
		{
			if (object.Equals(_selectGamepadInfo, value))
			{
				return;
			}
			_selectGamepadInfo = value;
			if (_selectGamepadInfo != null)
			{
				switch (_selectGamepadInfo.CpuType)
				{
				case "ch571":
					if (_selectGamepadInfo.Id == 7)
					{
						UpgradeHelpTip = StrResources.upgradeBS1HelpTip;
					}
					else
					{
						UpgradeHelpTip = StrResources.upgradeDongleHelpTip;
					}
					break;
				case "ch582":
					UpgradeHelpTip = StrResources.upgradeGamePadK1HelpTip;
					break;
				case "ch547":
					UpgradeHelpTip = StrResources.upgradeGamePadK1TriggerHelpTip;
					break;
				case "k2ch547":
					UpgradeHelpTip = StrResources.upgradeGamePadK2TriggerHelpTip;
					break;
				case "ch591":
					UpgradeHelpTip = StrResources.upgradeBS1HelpTip;
					break;
				default:
					UpgradeHelpTip = StrResources.GamePadHelpTip;
					break;
				}
				_wchIspManager.SetMcuType(_selectGamepadInfo.MucType);
				_wchIspManager.SetChipSeries(_selectGamepadInfo.ChipSeries);
				_wchIspManager.SetBootPinNumber(_selectGamepadInfo.BootPinNum);
				FLog.d("IsClearDataFlash" + IsClearDataFlash);
				_wchIspManager.SetClearDataFlash(IsClearDataFlash);
				StartFoundDeviceThread();
				new Thread((object? o) =>
				{
					CheckFirmwareVersion();
				}).Start();
			}
			RaisePropertyChanged("SelectGamepadInfo");
		}
	}

	public DelegateCommand CloseWindowCmd => _closeWindowCmd ?? (_closeWindowCmd = new DelegateCommand(ExecuteCloseWindowCmd));

	public string AppTitle
	{
		get
		{
			return _appTitle;
		}
		set
		{
			if (!string.Equals(_appTitle, value, StringComparison.Ordinal))
			{
				_appTitle = value;
				RaisePropertyChanged("AppTitle");
			}
		}
	}

	public string mClearDataFlashText
	{
		get
		{
			return _mClearDataFlashText;
		}
		set
		{
			if (!string.Equals(_mClearDataFlashText, value, StringComparison.Ordinal))
			{
				_mClearDataFlashText = value;
				RaisePropertyChanged("mClearDataFlashText");
			}
		}
	}

	public bool DialogResult
	{
		get
		{
			return _dialogResult;
		}
		set
		{
			if (_dialogResult != value)
			{
				_dialogResult = value;
				RaisePropertyChanged("DialogResult");
			}
		}
	}

	public ObservableCollection<FDGDeviceFirmware> GamepadInfo
	{
		get
		{
			return _gamepadInfo;
		}
		set
		{
			if (!object.Equals(_gamepadInfo, value))
			{
				_gamepadInfo = value;
				RaisePropertyChanged("GamepadInfo");
			}
		}
	}

	public ObservableCollection<FirmwareUpgreadeInfo> UpgreadeInfo
	{
		get
		{
			return _upgreadeInfo;
		}
		set
		{
			if (!object.Equals(_upgreadeInfo, value))
			{
				_upgreadeInfo = value;
				RaisePropertyChanged("UpgreadeInfo");
			}
		}
	}

	public ObservableCollection<ProductSnModel> ProductSn
	{
		get
		{
			return productSn;
		}
		set
		{
			if (!object.Equals(productSn, value))
			{
				productSn = value;
				RaisePropertyChanged("ProductSn");
			}
		}
	}

	public bool IsClearDataFlash
	{
		get
		{
			return isClearDataFlash;
		}
		set
		{
			if (isClearDataFlash != value)
			{
				isClearDataFlash = value;
				_wchIspManager.SetClearDataFlash(value);
				RaisePropertyChanged("IsClearDataFlash");
			}
		}
	}

	public string Title
	{
		get
		{
			throw new NotImplementedException();
		}
	}

	public bool IsShowTipInfo
	{
		get
		{
			return _IsShowTipInfo;
		}
		set
		{
			if (_IsShowTipInfo != value)
			{
				_IsShowTipInfo = value;
				RaisePropertyChanged("IsShowTipInfo");
			}
		}
	}

	public string TipInfo
	{
		get
		{
			return _TipInfo;
		}
		set
		{
			if (!string.Equals(_TipInfo, value, StringComparison.Ordinal))
			{
				_TipInfo = value;
				RaisePropertyChanged("TipInfo");
			}
		}
	}

	public event Action<IDialogResult> RequestClose;

	public FmUpgradeViewModel(IRegionManager _regionManager)
	{
		regionManager = _regionManager;
		_wchIspManager = new WchIspManager();
		_wchIspManager.DeviceConnected += OnDeviceConnected;
		_wchIspManager.DeviceDisconnected += OnDeviceDisconnected;
		InitData();
		GoConnectSuccessCommand = new DelegateCommand(StartUpdateGamePad);
		GoFirstCommand = new DelegateCommand(goCheckGamePadFirstStatus);
		if (!FirmwareWchDriver.chekDriversisExits())
		{
			ExecuteRepairDriverCmd();
		}
	}

	public void InitData()
	{
		if (_gamepadInfo == null)
		{
			_gamepadInfo = new ObservableCollection<FDGDeviceFirmware>
			{
				new FDGDeviceFirmware
				{
					Id = 3,
					Name = StrResources.GamePad_k1,
					CpuType = "ch582",
					MucType = 130,
					ChipSeries = 6,
					BootPinNum = 1,
					FirmName = "K1",
					DeviceType = "K1"
				},
				new FDGDeviceFirmware
				{
					Id = 4,
					Name = StrResources.GamePad_k1f1f2_dongle,
					CpuType = "ch571",
					MucType = 113,
					ChipSeries = 3,
					BootPinNum = 1,
					FirmName = "DONGLE",
					DeviceType = "Dongle"
				},
				new FDGDeviceFirmware
				{
					Id = 5,
					Name = StrResources.GamePad_k1_trigger,
					CpuType = "ch547",
					MucType = 71,
					ChipSeries = 2,
					BootPinNum = 0,
					FirmName = "K1TRIGGER",
					DeviceType = "K1"
				},
				new FDGDeviceFirmware
				{
					Id = 6,
					Name = StrResources.GamePad_k2_trigger,
					CpuType = "k2ch547",
					MucType = 71,
					ChipSeries = 2,
					BootPinNum = 0,
					FirmName = "K2TRIGGER",
					DeviceType = "K2"
				},
				new FDGDeviceFirmware
				{
					Id = 7,
					Name = StrResources.Product_BS1,
					CpuType = "ch571",
					MucType = 113,
					ChipSeries = 3,
					BootPinNum = 1,
					FirmName = "BS1",
					DeviceType = "BS1"
				},
				new FDGDeviceFirmware
				{
					Id = 8,
					Name = StrResources.Product_Name_BS2,
					CpuType = "ch591",
					MucType = 145,
					ChipSeries = 12,
					BootPinNum = 1,
					FirmName = "BS2",
					DeviceType = "BS2"
				},
				new FDGDeviceFirmware
				{
					Id = 8,
					Name = StrResources.Product_Name_BS2Pro,
					CpuType = "ch591",
					MucType = 145,
					ChipSeries = 12,
					BootPinNum = 1,
					FirmName = "BS2Pro",
					DeviceType = "BS2Pro"
				}
			};
		}
		if (_upgreadeInfo == null)
		{
			_upgreadeInfo = new ObservableCollection<FirmwareUpgreadeInfo>
			{
				new FirmwareUpgreadeInfo
				{
					Type = 1,
					Name = "升级手柄"
				},
				new FirmwareUpgreadeInfo
				{
					Type = 2,
					Name = "升级接收器"
				}
			};
		}
		if (productSn == null)
		{
			productSn = new ObservableCollection<ProductSnModel>
			{
				new ProductSnModel
				{
					Type = 1,
					ShowName = "NR"
				},
				new ProductSnModel
				{
					Type = 2,
					ShowName = "NL"
				}
			};
		}
		GamepadConnectStatus = StrResources.GamepadUnConnectStatus;
		IsIndicatorVisible = false;
		if (MainWindowViewModel.GetInstance().SelFDGDeviceFirmware != null)
		{
			string deviceType = MainWindowViewModel.GetInstance().SelFDGDeviceFirmware.DeviceType.ToLower();
			if (deviceType == "bs2proeva")
			{
				deviceType = "bs2pro";
			}
			if (deviceType == "bs1eva")
			{
				deviceType = "bs1";
			}
			SelectGamepadInfo = _gamepadInfo.FirstOrDefault((FDGDeviceFirmware t) => t.FirmName.ToLower() == deviceType);
		}
	}

	private void OnDeviceConnected(object sender, FDGDeviceFirmware deviceInfo)
	{
		FLog.d("设备已连接!");
		FLog.d(deviceInfo.ToString());
		UpdateGamePad(deviceInfo);
	}

	private void OnDeviceDisconnected(object sender, FDGDeviceFirmware deviceInfo)
	{
		FLog.d("设备已断开!");
		FLog.d(deviceInfo.ToString());
	}

	public void UpdateGamePad(FDGDeviceFirmware gamepadModel)
	{
		if (gamepadModel.IsConnect)
		{
			IsIndicatorVisible = false;
			ShowConnectButton = true;
			ShowUnConnectButton = false;
			ShowDownloadEndButton = false;
			GamepadConnectStatus = StrResources.StartUpgrade;
		}
	}

	public void Configure()
	{
	}

	private void ExecuteRepairDriverCmd()
	{
		Task.Run(() =>
		{
			FirmwareWchDriver.installDriver();
		});
	}

	public async void CheckFirmwareVersion()
	{
		FirmwareApiModel firmwareModel = FirmwareService.GetFirmware(SelectGamepadInfo.FirmName, SelectGamepadInfo.CpuType, SelectGamepadInfo.FirmwareVersion);
		if (firmwareModel != null)
		{
			UpgradeTitle = firmwareModel.title;
			UpgradeContent = firmwareModel.desc;
		}
		else
		{
			UpgradeTitle = "";
			UpgradeContent = "";
		}
	}

	public void goCheckGamePadFirstStatus()
	{
		SelectIndex = 0;
		ShowUnConnectButton = true;
		ShowConnectButton = false;
		ShowDownloadEndButton = false;
		GamepadConnectStatus = StrResources.GamepadUnConnectStatus;
		if (IsDownloadSuccess)
		{
			MainWindowViewModel.GetInstance().CLoseFirmwareWindow();
		}
	}

	public void StartUpdateGamePad()
	{
		if (IsDownloadSuccess)
		{
			return;
		}
		if (SelectGamepadInfo.Id != 7 && SelectGamepadInfo == null)
		{
			DownLoadFail();
			return;
		}
		if (!_wchIspManager.IsConnected)
		{
			DownLoadFail();
			return;
		}
		GamepadConnectStatus = StrResources.Downloading;
		IsIndicatorVisible = true;
		WchIspHelper.IsDownloading = true;
		FirmwareApiModel firewareModel = FirmwareService.GetFirmware(SelectGamepadInfo.FirmName, SelectGamepadInfo.CpuType, SelectGamepadInfo.FirmwareVersion);
		if (firewareModel == null)
		{
			return;
		}
		FLog.d("url:" + firewareModel.url);
		if (string.IsNullOrEmpty(firewareModel.url))
		{
			return;
		}
		Random random = new Random();
		string fileName = firewareModel.title + "_" + firewareModel.version + "_" + random.Next() + ".hex";
		string fileFullPath = FirmwareService.SavePath + fileName;
		new Thread(() =>
		{
			try
			{
				FirmwareService.DownloadFile(firewareModel.url, fileName, async (int progress) =>
				{
					if (progress >= 100)
					{
						DownloadProgress = 88;
					}
					else
					{
						DownloadProgress = progress;
					}
					if (progress == -1)
					{
						FLog.d("文件下载失败异常！");
						DownLoadFail();
					}
					if (progress < 80)
					{
						GamepadConnectStatus = StrResources.Downloading + progress + "%";
					}
					if (progress == 200)
					{
						Thread.Sleep(200);
						if (await _wchIspManager.DownloadFirmwareAsync(fileFullPath) == 1)
						{
							DownLoadSuccess();
						}
						else
						{
							FLog.d("芯片内容 下载失败！");
							DownLoadFail();
						}
					}
				});
			}
			catch (Exception ex)
			{
				FLog.LogException(ex);
				ALiErrLogUtils.SendLogToServer(ex);
				DownLoadFail();
			}
		}).Start();
	}

	public void DownLoadFail()
	{
		FLog.d("downLoadFail");
		ShowDownloadEndButton = true;
		ShowConnectButton = false;
		ShowUnConnectButton = false;
		WchIspHelper.IsDownloading = false;
		IsDownloadSuccess = false;
		StartFoundDeviceThread();
	}

	public void DownLoadSuccess()
	{
		GamepadConnectStatus = StrResources.DownloadSuccess;
		FLog.d("downLoadSuccess");
		ShowDownloadEndButton = true;
		ShowConnectButton = false;
		ShowUnConnectButton = false;
		IsDownloadSuccess = true;
		if (SelectGamepadInfo.CpuType.ToLower() == "ch547" || SelectGamepadInfo.CpuType.ToLower() == "k2ch547")
		{
			IsShowTipInfo = true;
			TipInfo = StrResources.Connect_Mode2_3_K1_old;
		}
		StartFoundDeviceThread();
	}

	public void StartFoundDeviceThread()
	{
		_wchIspManager.StopDeviceScan();
		_wchIspManager.StartDeviceScan();
	}

	public bool CanCloseDialog()
	{
		return true;
	}

	public void OnDialogClosed()
	{
		_wchIspManager.StopDeviceScan();
	}

	public void OnDialogOpened(IDialogParameters parameters)
	{
	}

	private void ExecuteCloseWindowCmd()
	{
		_wchIspManager.StopDeviceScan();
		CloseWindowCmd.Execute();
	}
}
