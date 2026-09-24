"""Fetch a pinned Windows render pack at BUILD time, never at customer setup."""
import hashlib,pathlib,shutil,tempfile,urllib.request,zipfile
ROOT=pathlib.Path(__file__).resolve().parents[1]
URL='https://www.gyan.dev/ffmpeg/builds/packages/ffmpeg-8.1.2-essentials_build.zip'
SHA256='db580001caa24ac104c8cb856cd113a87b0a443f7bdf47d8c12b1d740584a2ec'
def main():
 target=ROOT/'vendor/ffmpeg';target.parent.mkdir(parents=True,exist_ok=True)
 with tempfile.TemporaryDirectory() as tmp:
  archive=pathlib.Path(tmp)/'ffmpeg.zip';digest=hashlib.sha256()
  with urllib.request.urlopen(URL,timeout=120) as response,archive.open('wb') as out:
   while chunk:=response.read(1024*1024):out.write(chunk);digest.update(chunk)
  if digest.hexdigest()!=SHA256:raise RuntimeError('FFmpeg checksum mismatch; download rejected.')
  with zipfile.ZipFile(archive) as z:
   for name in z.namelist():
    path=(pathlib.Path(tmp)/name).resolve()
    if not path.is_relative_to(pathlib.Path(tmp).resolve()):raise RuntimeError('Unsafe archive path')
   z.extractall(tmp)
  source=next(pathlib.Path(tmp).glob('ffmpeg-*/bin/ffmpeg.exe')).parents[1]
  if target.exists():shutil.rmtree(target)
  shutil.copytree(source,target)
  (target/'DOWNLOAD.txt').write_text(f'URL: {URL}\nSHA256: {SHA256}\n',encoding='utf8')
  (target/'bin/ffplay.exe').unlink(missing_ok=True)
 print('Verified FFmpeg/ffprobe and upstream notices staged.')
if __name__=='__main__':main()
