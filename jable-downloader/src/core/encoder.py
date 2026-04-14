import subprocess


def ffmpeg_encode(input_path, output_path):
    command = [
        'ffmpeg', '-hide_banner', '-loglevel', 'error',
        '-i', input_path,
        '-c', 'copy', '-bsf:a',
        'aac_adtstoasc', '-movflags',
        '+faststart', output_path
    ]

    result = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

    if result.returncode != 0:
        print(f'  [!] ffmpeg: {result.stderr.decode(errors="replace").strip()}')
        return False

    return True
