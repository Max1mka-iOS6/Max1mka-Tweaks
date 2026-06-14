import urllib.request
import urllib.error
import http.cookiejar
from http.server import BaseHTTPRequestHandler, HTTPServer
import socketserver

class ThreadingHTTPServer(socketserver.ThreadingMixIn, HTTPServer):
    daemon_threads = True

# Настраиваем глобальную сессию с куками
cookie_jar = http.cookiejar.CookieJar()
opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cookie_jar))
opener.addheaders = [
    ('User-Agent', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'),
    ('Accept', 'application/json, text/javascript, */*; q=0.01'),
    ('Connection', 'keep-alive')
]
urllib.request.install_opener(opener)

def refresh_cookies():
    print("[*] Обновляем куки сессии (притворяемся браузером)...")
    try:
        req = urllib.request.Request("https://old.reddit.com/")
        req.add_header('Accept', 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8')
        urllib.request.urlopen(req)
        print("    [+] Куки успешно получены!")
    except Exception as e:
        print(f"    [-] Не удалось получить куки: {e}")

# Получаем куки при запуске сервера
refresh_cookies()

class ProxyHTTPRequestHandler(BaseHTTPRequestHandler):
    protocol_version = 'HTTP/1.1'
    
    def do_GET(self):
        path = self.path
        
        # Исправляем баг Alien Blue, который не раскодирует &amp; в ссылках на картинки
        if '&amp;' in path:
            path = path.replace('&amp;', '&')
            
        if path.startswith('/www.reddit.com'):
            path = path.replace('/www.reddit.com', '', 1)
            
        original_host = self.headers.get('X-Original-Host', 'old.reddit.com')
        
        # Если это запрос к API/Reddit, используем old.reddit.com
        if 'reddit.com' in original_host:
            target_url = "https://old.reddit.com" + path
        else:
            # Если это картинки (redd.it, imgur и т.д.), обращаемся к оригинальному хосту
            target_url = f"https://{original_host}" + path
            
        print(f"[*] Запрос: {target_url}")
        
        req = urllib.request.Request(target_url)
        
        try:
            response = urllib.request.urlopen(req, timeout=15)
            data = response.read()
            
            self.send_response(response.getcode())
            content_type = response.info().get('Content-Type', 'application/json; charset=UTF-8')
            self.send_header('Content-Type', content_type)
            self.send_header('Content-Length', str(len(data)))
            self.send_header('Access-Control-Allow-Origin', '*')
            
            cookies = response.info().get_all('Set-Cookie')
            if cookies:
                for c in cookies:
                    self.send_header('Set-Cookie', c)
                    
            self.end_headers()
            self.wfile.write(data)
            print(f"    [+] Успешно отдано на iPod! ({content_type})")
            
        except urllib.error.HTTPError as e:
            if e.code == 403:
                print("    [-] Ошибка 403: Куки устарели, пробуем обновить...")
                refresh_cookies()
                try:
                    response = urllib.request.urlopen(req, timeout=15)
                    data = response.read()
                    self.send_response(response.getcode())
                    content_type = response.info().get('Content-Type', 'application/json; charset=UTF-8')
                    self.send_header('Content-Type', content_type)
                    self.send_header('Content-Length', str(len(data)))
                    self.send_header('Access-Control-Allow-Origin', '*')
                    self.end_headers()
                    self.wfile.write(data)
                    print(f"    [+] Успех после обновления кук! ({content_type})")
                    return
                except Exception as inner_e:
                    print(f"    [-] Повторная ошибка: {inner_e}")
                    
            print(f"    [-] Ошибка от Reddit: {e.code}")
            self.send_response(e.code)
            self.end_headers()
        except Exception as e:
            print(f"    [-] Системная ошибка: {e}")
            self.send_response(500)
            self.end_headers()

    def do_POST(self):
        path = self.path
        if '&amp;' in path:
            path = path.replace('&amp;', '&')
        if path.startswith('/www.reddit.com') or path.startswith('/ssl.reddit.com'):
            path = path.replace('/www.reddit.com', '', 1).replace('/ssl.reddit.com', '', 1)
            
        original_host = self.headers.get('X-Original-Host', 'old.reddit.com')
        
        if 'reddit.com' in original_host:
            target_url = "https://old.reddit.com" + path
        else:
            target_url = f"https://{original_host}" + path
            
        print(f"[*] POST Запрос: {target_url}")
        
        content_length = int(self.headers.get('Content-Length', 0))
        post_data = self.rfile.read(content_length)
        
        req = urllib.request.Request(target_url, data=post_data, method='POST')
        
        if 'Content-Type' in self.headers:
            req.add_header('Content-Type', self.headers['Content-Type'])
            
        try:
            response = urllib.request.urlopen(req, timeout=15)
            data = response.read()
            
            self.send_response(response.getcode())
            content_type = response.info().get('Content-Type', 'application/json; charset=UTF-8')
            self.send_header('Content-Type', content_type)
            self.send_header('Content-Length', str(len(data)))
            self.send_header('Access-Control-Allow-Origin', '*')
            
            # Прокидываем куки авторизации на айпод!
            cookies = response.info().get_all('Set-Cookie')
            if cookies:
                for c in cookies:
                    self.send_header('Set-Cookie', c)
                    
            self.end_headers()
            self.wfile.write(data)
            print(f"    [+] POST Успешно отдан! ({content_type})")
            
        except urllib.error.HTTPError as e:
            data = e.read()
            self.send_response(e.code)
            content_type = e.info().get('Content-Type', 'application/json; charset=UTF-8')
            self.send_header('Content-Type', content_type)
            self.send_header('Content-Length', str(len(data)))
            self.send_header('Access-Control-Allow-Origin', '*')
            
            cookies = e.info().get_all('Set-Cookie')
            if cookies:
                for c in cookies:
                    self.send_header('Set-Cookie', c)
                    
            self.end_headers()
            self.wfile.write(data)
            print(f"    [-] POST Ошибка от Reddit: {e.code}")
        except Exception as e:
            print(f"    [-] Критическая ошибка POST: {e}")
            self.send_response(500)
            self.end_headers()

import os

def run(server_class=ThreadingHTTPServer, handler_class=ProxyHTTPRequestHandler):
    port = int(os.environ.get('PORT', 5000))
    server_address = ('0.0.0.0', port)
    httpd = server_class(server_address, handler_class)
    print(f"==================================================")
    print(f"Alien Blue Proxy Server запущен на порту {port}")
    print(f"==================================================")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    httpd.server_close()

if __name__ == '__main__':
    run()
