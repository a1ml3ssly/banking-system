import importlib.util
import os
import sys

banking_api_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'banking_api')
sys.path.insert(0, banking_api_dir)

spec = importlib.util.spec_from_file_location('app', os.path.join(banking_api_dir, 'app.py'))
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
app = module.app

if __name__ == '__main__':
    port = int(os.getenv('API_PORT', 5000))
    print(f'\n  Banking API running at  http://0.0.0.0:{port}')
    print(f'  Swagger UI available at http://0.0.0.0:{port}/docs\n')
    app.run(host='0.0.0.0', port=port, debug=True)
