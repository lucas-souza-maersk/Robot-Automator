import requests
import logging

LEVEL_MAP = {
    "INFO": 1,
    "WARNING": 2,
    "CRITICAL": 3
}

CONFIG_LEVEL_MAP = {
    "Info (Sucessos)": 1,
    "Erros & Avisos": 2,
    "Apenas Crítico": 3
}

class TeamsAlertManager:
    def __init__(self, alert_config, logger):
        self.config = alert_config
        self.logger = logger
        
        self.enabled = self.config.get('enabled', False)
        self.webhook_url = self.config.get('webhook_url')
        
        config_level_str = self.config.get('level', 'Apenas Crítico')
        self.configured_level_value = CONFIG_LEVEL_MAP.get(config_level_str, 3)

        if self.enabled and not self.webhook_url:
            self.logger.warning("Alertas do Teams (Workflow) estão habilitados, mas nenhum Webhook URL foi configurado.")
            self.enabled = False
        elif self.enabled:
             self.logger.info(f"AlertManager do Teams (Workflow) inicializado. Nível de alerta: {config_level_str}")

    def send(self, level, title, message):
        if not self.enabled:
            return

        alert_level_value = LEVEL_MAP.get(level, 1)

        if alert_level_value < self.configured_level_value:
            return

        full_message_text = ""
        if level == "CRITICAL":
            full_message_text = f"🚨 {level}: {title}\n\n{message}"
        elif level == "WARNING":
            full_message_text = f"🟠 {level}: {title}\n\n{message}"
        else: 
            full_message_text = f"✅ {level}: {title}\n\n{message}"

        try:
            payload = {
                "message": full_message_text
            }

            response = requests.post(self.webhook_url, json=payload, timeout=10)
            response.raise_for_status()

        except Exception as e:
            self.logger.error(f"Falha ao enviar alerta do Teams (Workflow): {e}")