import sys


class Logger:
    STATUS_OK = '  OK'
    STATUS_SKIP = 'SKIP'
    STATUS_FAIL = 'FAIL'

    def __init__(self):
        self.results = []

    def header(self, text):
        width = max(60, len(text) + 4)
        print(f'\n{"=" * width}')
        print(f'  {text}')
        print(f'{"=" * width}')

    def info(self, text):
        print(text)

    def warn(self, text):
        print(f'  [!] {text}', file=sys.stderr)

    def video_start(self, index, total, title):
        print(f'\n[{index}/{total}] {title}')

    def video_done(self, index, total, status, detail=''):
        tag = f'[{status}]'
        msg = f'  {tag} [{index}/{total}]'
        if detail:
            msg += f' {detail}'
        print(msg)

    def record(self, index, video_id, title, status, detail=''):
        self.results.append({
            'index': index,
            'video_id': video_id,
            'title': title,
            'status': status,
            'detail': detail,
        })

    def print_summary(self):
        if not self.results:
            return

        ok = [r for r in self.results if r['status'] == self.STATUS_OK]
        skipped = [r for r in self.results if r['status'] == self.STATUS_SKIP]
        failed = [r for r in self.results if r['status'] == self.STATUS_FAIL]

        print(f'\n{"=" * 60}')
        print(f'  Summary: {len(ok)} done, {len(skipped)} skipped, {len(failed)} failed'
              f'  (total {len(self.results)})')
        if failed:
            print(f'{"─" * 60}')
            print('  Failed:')
            for r in failed:
                print(f'    {r["video_id"]}  {r["detail"]}')
        print(f'{"=" * 60}')
