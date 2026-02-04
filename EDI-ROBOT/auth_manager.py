import config_manager
import n4_connector
# import pyodbc (Descomente se tiver instalado para usar SQL)

def authenticate_user(username, password):
    settings = config_manager.load_settings()
    method = settings.get("auth_method", "N4")

    if method == "N4":
        url = settings.get("n4_url")
        scope = settings.get("n4_scope")
        return n4_connector.check_n4_credentials(url, scope, username, password)
    
    elif method == "DATABASE":
        # Logica simples de banco (Exemplo)
        # db = settings.get("db_config")
        # Implementar conexao SQL aqui
        # Por enquanto retorna True para teste se user for admin
        return (username == "admin" and password == "admin") 
    
    return False