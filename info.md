# pyvisa + pyvisa-py + GPIB/Serialによる測定機器の制御

# 1. 接続例

1. LAN/GPIB(Serial) Gatewayを用いて、TCP/IP接続をする。

1. USB-GPIB, USB-Serial converterを用いて、USB経由で接続する。

実際には、1の方法ではAgilent E5810 LAN/GPIB Gatewayを、
2の方法ではAgilent 82357B (USB-GPIB), Sanwa CVRS9 (USB-Serial)を使った。

1のLANを用いる方法はpython+pipのみで環境が構築できるため、windows, mac, linuxいずれも可。
また、PCからワイヤレスで制御ができるので、環境構築後の使いやすさの面でもこちらが楽。
装置のマニュアルを読み、あらかじめ適当な固定IPアドレスを設定しておく。

2の方法では、使うUSBコンバータによって対応可能な環境が変わる。
例えば、Agilent82357bは32bitのLinuxでしか接続することができなかった。
以降の環境構築方法は64bitでも同じだが、Agilent82357bには接続できないので注意。
(値段はするが、NI社のUSBコンバータを使えばMac, 64bitのLinux等から接続可能。
ただし、Macにlinux-gpibを導入する方法は不明なので、代わりにNI-VISAを使う。)

# 2. Install linux-gpib (2のみ)
以下では、2(USB接続)をする場合にのみ必要なlinux-gpibの導入手順を記述している。
__この手順は1(LAN接続)をする場合には不要__

## 2.1. Install required packages

```Shell
sudo apt update
sudo apt upgrade

sudo apt install build-essential linux-headers-$(uname -r) python python-dev python3 python3-dev fxload
```

## 2.2. Install linux-gpib

### 2.2.1 Build
linux-gpib-4.0.4 (2017年現在の最新版)を[公式サイト](https://linux-gpib.sourceforge.io/)からダウンロード。
古いlinux-gpibにはバグがあるため、Linuxのカーネルが4.X.Xの場合linux-gpib >= 4.0.3が必要。

また、linux-gpibと同時にインストールされるpythonライブラリはpython2にしか対応していないので、
python3からも使えるよう、language/python以下のソースコードを編集する。
具体的には、Gpib.pyとgpibinter.cを[こちら](https://github.com/yurutaso/pyvisa-example)に修正し、以下の手順で手動でインストールする。

```Shell
cd '/path/to/linux-gpib-4.0.4.tar.gz'
tar zxvf linux-gpib-4.0.4.tar.gz
cd linux-gpib-4.0.4

./configure # pythonがyesになっていることを確認。
make
sudo make install

# gpib_configからlibraryが使えるよう、シンボリックリンクを作成しておく
sudo ln -s /usr/local/lib/libgpib.so.0 /lib/libgpib.so.0

# python3からも使えるよう、以下を実行
cd language
cp -r python python3
cd python3
# Gpib.py, gpibinter.cを上のものに置き換える
# 元のファイルは適当にバックアップをとる
mv Gpib.py Gpib.py.bak
mv gpibinter.py gpibinter.py.bak
mv 'Path/to/new/Gpib.py' Gpib.py
mv 'Path/to/new/gpibinter.c' gpibinter.c
# pythonのライブラリをBuildし直す
make clean
make
# make installだとpython2にインストールされるので、手動でpython3にインストールする
sudo python3 setup.py install

# python, python3でimport gpib, import Gpibができることを確認
```

### 2.2.2 Edit /etc/gpib.conf

- board_typeを"agilent_82357a"に変更する(82357bを使う場合でも82357aとする)
- padで指定した値は後で使う (pad=0 -> /dev/gpib0 で接続)
- deviceの項を設定すると、pythonで操作する際、GPIB addressではなく名前で開けるようになる。直接addressで接続することも可能なため必須ではない。ここでは、アドレスが11の温度計を設定している。

```C
interface {
        minor = 0       /* board index, minor = 0 uses /dev/gpib0, minor = 1 uses /dev/gpib1, etc. */
        board_type = "agilent_82357a"   /* type of interface board being used */
        name = "violet" /* optional name, allows you to get a board descriptor using ibfind() */
        pad = 0 /* primary address of interface             */
        sad = 0 /* secondary address of interface           */
        timeout = T3s   /* timeout for commands */

        eos = 0x0a      /* EOS Byte, 0xa is newline and 0xd is carriage return */
        set-reos = yes  /* Terminate read if EOS */
        set-bin = no    /* Compare EOS 8-bit */
        set-xeos = no   /* Assert EOI whenever EOS byte is sent */
        set-eot = yes   /* Assert EOI with last byte on writes */

/* settings for boards that lack plug-n-play capability */
        base = 0        /* Base io ADDRESS                  */
        irq  = 0        /* Interrupt request level */
        dma  = 0        /* DMA channel (zero disables)      */

/* pci_bus and pci_slot can be used to distinguish two pci boards supported by the same driver */
/*      pci_bus = 0 */
/*      pci_slot = 7 */

        master = yes    /* interface board is system controller */
}

// deviceの書き換え (deviceの名前はなんでも良い。padは、GPIBをつなぐ装置のGPIBアドレスで、装置側で設定する)
// 装置が複数ある場合、その数だけdeviceの項を追加する。

device {
        minor = 0       /* minor number for interface board this device is connected to */
        name = "thermometer"    /* device mnemonic */
        pad = 11        /* The Primary Address */
        sad = 0 /* Secondary Address */

        eos = 0xa       /* EOS Byte */
        set-reos = no /* Terminate read if EOS */
        set-bin = no /* Compare EOS 8-bit */
}
```

### 2.2.3 Kernel moduleにgpibを追加

```Shell
# Kernelは自分のものに合わせる
uname -r # 4.8.0-58-generic
sudo insmod /lib/modules/4.8.0-58-generic/gpib/sys/gpib_common.ko
sudo insmod /lib/modules/4.8.0-58-generic/gpib/agilent_82357a/agilent_82357a.ko
lsmod # 今追加した2つがあることを確認
```

## 2.3. firmwareの導入

http://linux-gpib.sourceforge.net/firmware/ から最新版(2008-08-10)をダウンロード。
適当な場所に移動しておく。

```Shell
tar zxvf firmware-2008-08-10.tar.gz
```

## 2.4. 動作チェック

```Shell
# GPIB-USBのUSB端子をPCに接続 (赤のランプのみが光るはず)

# busとdevの番号を確認
lsusb
# e.g. Bus 001 Device 003: ID ...

# その番号を使ってgpibと接続 (さきほどダウンロードしたfirmwareを読み込む)
sudo fxload -t fx2 -D /dev/bus/usb/001/003 -I /usr/share/usb/xxx/yyy.hex

# devの番号が一つ上がっていることを確認
lsusb
# e.g. Bus 001 Device 004: ID ...

# もう一度gpibと接続 (devの番号を一つ増やす) (緑のランプが光る)
sudo fxload -t fx2 -D /dev/bus/usb/001/004 -I hoge/agilent_82357a/measat_releaseX1.8.hex

# permissionの変更 (gpibの番号は /etc/gpib.conf に合わせる. 通常は0)
sudo chmod 666 /dev/gpib0

# Linux-gpibのロード
sudo gpib_config
# USBを再接続した場合等、すでにgpib_confを行っていた場合はおそらく不要(後でエラーになる?)


# 動作チェック (chmodをしていない場合 sudo が必要)
ibtest

## ibtest ####################
# [d]eviceを選択
# gpibのアドレスを入力
# [w]rite
# *IDN?
# [r]ead
#
# で装置の名前が返されればOK("*IDN?"は装置の名前を聞くGPIBの命令)
##############################

# Ubuntu-64bitでは、ibtestで何をしてもstatus=14のErrorがでてしまった。
# Agilent82357bが32bitにしか対応していないため、おそらくlinux-gpibというよりもこの機器特有の問題。
# NI社のGPIB-USBなどを使う場合は、おそらく64bitでも問題ない

```

## 2.5. pythonからの制御テスト

```python
import Gpib
# Gpibがimport出来ない場合、linux-gpibのconfigure時にpythonが無効になっている。
# python-devがinstallされていることを確認し、もう一度linux-gpibのconfigureからやり直す。
# python3から使う場合も、configureではpython2のライブラリを探しているので、python-devは必要

device = Gpib.Gpib(0, pad=11)
device.write("*IDN?")
device.read()
# ibtestで表示されたのと同じdeviceの名前が表示されればOK
```

## 2.6. 2回目以降の接続について

初期設定を済ましている場合、USBを差し込んでからpythonで制御するまで

1. USBの差し込み
1. lsusb -> fxload -> lsusb -> fxload
1. chmod 666 /dev/gpib0
1. gpib_config

をすればよい(適宜sudoをいれる)。
Agilent 82357bのfirmware(measat_releaseX1.8.hex)を/usr/share/usb/agilent_82357a/measat_releaseX1.8.hexに移動しておくと、USB差し込み時にfxloadの部分を自動でやってくれるらしいが、未確認。

# 3. Install pyserial (2のみ)
serialの設定はmac, linuxどちらの場合も以下を実行するだけ。
__この手順もLAN経由で接続をする場合は不要__

```shell
pip3 install --upgrade pyserial
```

# 4. Install pyvisa, pyvisa-py (1, 2共通)

```Shell
pip3 install PyVISA PyVISA-py

# Ubuntuの場合、以下でも可
sudo apt install python3-pyvisa-py
```


# 5. Example

以上で環境が構築されているはず。`python3 -m visa info`を実行するとgpib, serialがpyvisaから認識されているか確認できる。
1の方法を使う場合、TCPIP INSTR, TCPIP SOCKETが AvailableであればOK(通常は何もしないでも問題ない)。
2の方法を使う場合、GPIB INSTRとASRL INSTRがAvailableであることを確認。
これが問題なければ、ここにあるinstruments.pyを使って以下のように接続が可能

```python
import visa
rm = visa.ResourceManager('@py')

#ip = 'xxx.yyy.zzz.www'
#port = '0'
#address = '26'
# 1の場合、TCPIP::xxx.yyy.zzz.www::gpib0,26::INSTR
# 2の場合、GPIB0::26::INSTR

inst = rm.open_resource('TCPIP::xxx.yyy.zzz.www::gpib0,26::INSTR')
inst.write('*IDN?')
name = inst.read()
# 装置の名前が表示されればOK
print(name)
```

# 6. Common error

1. gpib, serialのpermissionを(/dev/gpib0 etc)666に変更していない
1. USB-serial converterに接続するserial-serialケーブルの種類(ストレート、インターリンクetc)が違う(装置ごとにどのケーブルを使うかが異なるのでピンアサインをマニュアルで確認する)
1. Linuxカーネルを更新した場合、linux-gpibの再ビルドが必要な場合がある。この場合、linux-gpibインストールの手順をやり直す。
