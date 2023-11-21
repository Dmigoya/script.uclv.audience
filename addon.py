import xbmc
import xbmcgui
import json
import requests
import os
from datetime import datetime
import shutil
import uuid
import subprocess

# globals
configPath = '/Users/davidmigoya/Library/Application Support/Kodi/addons/script.uclv.audience/config.json'
jwt = ''


# View
def notification(tittle, message, time):
    configs = readConfigs()
    if configs['isDebug']:
        dialog = xbmcgui.Dialog()
        dialog.notification(tittle, message, xbmcgui.NOTIFICATION_INFO, time)


def dialog(tittle, message):
    configs = readConfigs()
    if configs['isDebug']:
        dialog = xbmcgui.Dialog()
        dialog.ok(tittle, message)


def dialogYesNoCopyFileDataToUSB(tittle, message, pathUSB):
    configs = readConfigs()
    if configs['isDebug']:
        dialog = xbmcgui.Dialog()
        isPresedYes = dialog.yesno(tittle, message)
        if isPresedYes:
            return copyDataFile(pathUSB)
        else:
            return False
    else:
        return copyDataFile(pathUSB)


def dialogYesNoRemovedFileData(tittle, message):
    configs = readConfigs()
    flag = False
    if configs['isDebug']:
        dialog = xbmcgui.Dialog()
        flag = dialog.yesno(tittle, message)
    else:
        flag = configs['removeDataWhenCopyToUSB']
    if flag:
        removeDataFile()
    return flag


# Data
def readConfigs():
    global configPath
    try:
        with open(configPath) as f:
            return json.load(f)
    except Exception as e:
        notification("Audiometer", f"Error al leer configuraciones: {e}", 5000)
        return {}


def writeData(data):
    if not isSpaceAvaiable():
        notification('Audiometer', 'No hay espacio en el disco', 10000)
        return
    configs = readConfigs()
    path = configs['master_path'] + configs['data_name_file']
    fileJson = readData()
    if fileJson != None and 'data' in fileJson:
        fileJson['data'].append(data)
    else:
        fileJson = {'data': []}
        fileJson['data'].append(data)

    with open(path, 'w') as f:
        json.dump(fileJson, f)


def readData():
    configs = readConfigs()
    path = configs['master_path'] + configs['data_name_file']
    try:
        with open(path) as f:
            return json.load(f)
    except FileNotFoundError:
        data = {}
        with open(path, 'w') as f:
            json.dump(data, f)
        return data


def getModelDataToSave(name, timeIn):
    data = {}
    data['name'] = name
    data['time_in'] = timeIn.strftime('%Y-%m-%dT%H:%M:%S.%f')
    data['time_out'] = datetime.now().strftime('%Y-%m-%dT%H:%M:%S.%f')
    return data


def removeDataFile():
    configs = readConfigs()
    path = configs['master_path'] + configs['data_name_file']
    if os.path.exists(path):
        os.remove(path)


def existDataFile():
    configs = readConfigs()
    path = configs['master_path'] + configs['data_name_file']
    return os.path.exists(path)


def copyDataFile(pathEnd):
    configs = readConfigs()
    try:
        current_date_time = datetime.now().strftime("%Y%m%d_%H%M%S")

        uuid = getUUID()
        original_name = configs['data_name_file']
        base_name, extension = original_name.rsplit('.', 1)
        new_name = f"{base_name}_{uuid}_{current_date_time}.{extension}"

        pathIn = configs['master_path'] + original_name
        pathEndComplete = pathEnd + '/' + new_name

        shutil.copy(pathIn, pathEndComplete)
        return True
    except Exception as e:
        return False


def isSpaceAvaiable():
    configs = readConfigs()
    path = configs['master_path']
    dataFile = configs['data_name_file']
    if os.path.exists(path):
        statvfs = os.statvfs(path)
        freeSpace = statvfs.f_bavail * statvfs.f_frsize
        if os.path.exists(path + dataFile):
            sizeFile = os.path.getsize(path + dataFile)
            freeSpace = freeSpace - sizeFile
        if freeSpace > configs["max_space_kb"]:
            return True
        else:
            return False
    else:
        return False


def findUSB():
    configs = readConfigs()
    usbName = configs['usbName']
    result = subprocess.run(['df'], capture_output=True, text=True)
    lines = result.stdout.split('\n')
    for line in lines:
        parts = line.split()
        if len(parts)>0 and '/' in parts[-1]  and usbName == parts[-1].split('/')[-1]:
            return parts[-1]
    return ''


def getUUID():
    return str(uuid.getnode())


# API
def getTokenJWT():
    configs = readConfigs()
    urlbase = configs["url_api"] + ":" + configs["port_api"]
    url = urlbase + "/api/v1/login"

    payload = json.dumps({
        "userName": configs['userName'],
        "password": configs['password']
    })
    headers = {
        'Content-Type': 'application/json'
    }

    try:
        response = requests.request("POST", url, headers=headers, data=payload)
        if response.status_code == 200:
            return response.json()['token']
        else:
            notification("Audiometer", f"Error al obtener token JWT: {response.status_code}", 5000)
            return ''
    except Exception as e:
        notification("Audiometer", f"Error en la solicitud de JWT: {e}", 5000)
        return ''


def sendData():
    if not existDataFile():
        return True
    configs = readConfigs()
    baseUrl = configs["url_api"] + ":" + configs["port_api"]
    url = baseUrl + "/api/v1/data/saveData"
    payload = readData()
    global jwt
    token = jwt
    if token == '':
        token = getTokenJWT()
        if token == '':
            return False
        else:
            jwt = token
    token = "Bearer " + token

    headers = {
        "Authorization": token,
        'Content-Type': 'application/json'}

    try:
        response = requests.post(url, data=json.dumps(payload), headers=headers)
        if response.status_code == 200:
            if configs['removeDataWhenSendToServer']:
                removeDataFile()
            return True
        else:
            if response.text == 'Invalid token':
                jwt = ''
                sendData()
    except Exception as e:
        return False


def copyToUSBLogic():
    if not existDataFile():
        return
    pathUSB = findUSB()
    if pathUSB != '':
        copied = dialogYesNoCopyFileDataToUSB("Audiometer", "Copiar los datos registrados en la USB ", pathUSB)
        if copied:
            deleted = dialogYesNoRemovedFileData("Audiometer", "Eliminar los datos ya copiados")
            if deleted:
                notification("Audiometer", "Datos copiados y eliminados", 5000)
            else:
                notification("Audiometer", "Datos copiados", 5000)
        else:
            notification("Audiometer", "Error al copiar los datos", 5000)


# test-------------------------------------------------------------------------

# main-------------------------------------------------------------------------
notification("Audiometer", "The addon is running", 5000)
configs = readConfigs()
timeIn = datetime.now()
flagSaveDone = True
name = ''

# logic
while True:
    if xbmc.Player().isPlaying():
        flagSaveDone = False
        if name == '':
            name = xbmc.getInfoLabel("Player.Title")
            timeIn = datetime.now()
            xbmc.sleep(1000 * configs["sleep_time"])
            continue
        if xbmc.getInfoLabel("Player.Title") != name:
            data = getModelDataToSave(name, timeIn)
            writeData(data)
            name = xbmc.getInfoLabel("Player.Title")
            timeIn = datetime.now()
            xbmc.sleep(1000 * configs["sleep_time"])
            continue
    else:
        if not flagSaveDone:
            data = getModelDataToSave(name, timeIn)
            writeData(data)
            name = ''
            flagSaveDone = True
            xbmc.sleep(1000 * configs["sleep_time"])
            continue
    if not sendData():
        copyToUSBLogic()

# duration = xbmc.getInfoLabel("Player.Time")
# videoFormat = xbmc.getInfoLabel("Player.VideoCodec")
# audioFormat = xbmc.getInfoLabel("Player.AudioCodec")
