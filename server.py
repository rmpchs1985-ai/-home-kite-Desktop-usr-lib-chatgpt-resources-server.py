"""Local server for ARC. Set HOME_ASSISTANT_URL, HOME_ASSISTANT_TOKEN and APPLIANCES_JSON to enable real appliance control."""
import json, os, urllib.parse, urllib.request
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
ROOT = Path(__file__).parent
DEMO_STATES = {"light": "off", "fan": "off", "tv": "off", "plug": "off"}
APPLIANCES = json.loads(os.getenv("APPLIANCES_JSON", '{"light":"light.living_room", "fan":"fan.living_room", "tv":"media_player.tv", "plug":"switch.smart_plug"}'))
class ArcHandler(SimpleHTTPRequestHandler):
    def do_GET(self):
        if self.path.startswith('/api/weather'):
            query = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
            try:
                lat, lon = float(query['latitude'][0]), float(query['longitude'][0])
                url = f'https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&current=temperature_2m,wind_speed_10m'
                with urllib.request.urlopen(url, timeout=8) as response: current = json.load(response)['current']
                return self.send_json(200, {"temperature": current['temperature_2m'], "windSpeed": current['wind_speed_10m']})
            except (KeyError, ValueError, urllib.error.URLError, TimeoutError): return self.send_json(502, {"error": "Weather service unavailable"})
        return super().do_GET()
    def do_POST(self):
        if self.path != '/api/appliance': return self.send_json(404, {"error": "Not found"})
        try:
            size = int(self.headers.get('Content-Length', 0)); data = json.loads(self.rfile.read(size)); device, action = data['device'], data['action']
            if device not in APPLIANCES or action not in ('on', 'off'): raise ValueError
        except (ValueError, KeyError, json.JSONDecodeError): return self.send_json(400, {"error": "Invalid appliance command"})
        base, token = os.getenv('HOME_ASSISTANT_URL'), os.getenv('HOME_ASSISTANT_TOKEN')
        if not base or not token:
            DEMO_STATES[device] = action
            return self.send_json(200, {"message": f"Demo mode: {device} is now {action}. Configure Home Assistant to control real hardware."})
        entity = APPLIANCES[device]; domain = entity.split('.', 1)[0]
        request = urllib.request.Request(f'{base.rstrip("/")}/api/services/{domain}/turn_{action}', data=json.dumps({"entity_id": entity}).encode(), method='POST', headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(request, timeout=10): pass
            return self.send_json(200, {"message": f"{device} turned {action}."})
        except urllib.error.URLError: return self.send_json(502, {"error": "Home Assistant request failed"})
    def send_json(self, status, data):
        body = json.dumps(data).encode(); self.send_response(status); self.send_header('Content-Type', 'application/json'); self.send_header('Content-Length', str(len(body))); self.end_headers(); self.wfile.write(body)
if __name__ == '__main__':
    os.chdir(ROOT); print('ARC running at http://localhost:8080'); ThreadingHTTPServer(('', 8080), ArcHandler).serve_forever()
