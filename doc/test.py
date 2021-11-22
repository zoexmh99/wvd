
import codecs
def read_file(filename):
    ifp = codecs.open(filename, 'r', encoding='utf8')
    data = ifp.read()
    ifp.close()
    return data



data = read_file(r"C:\SJVA3\data\widevine_downloader\client\tmp\netflix\80010747\80010747.ja.force.vtt")

print(data)


tmp = data.split('\n')
print(tmp[18:])

