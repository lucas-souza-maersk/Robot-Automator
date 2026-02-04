import requests
import base64

def check_n4_credentials(url, scope_dict, username, password):
    # XML validado no teste "Rei"
    xml_payload = f"""<soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/" 
                      xmlns:ser="http://www.navis.com/services/argoservice"
                      xmlns:typ="http://types.webservice.argo.navis.com/v1.0">
       <soapenv:Header/>
       <soapenv:Body>
          <ser:genericInvoke>
             <ser:scopeCoordinateIdsWsType>
                <typ:operatorId>{scope_dict['op']}</typ:operatorId>
                <typ:complexId>{scope_dict['cpx']}</typ:complexId>
                <typ:facilityId>{scope_dict['fac']}</typ:facilityId>
                <typ:yardId>{scope_dict['yard']}</typ:yardId>
             </ser:scopeCoordinateIdsWsType>
             <ser:xmlDoc>
                <![CDATA[
                <query>
                    <entityName>User</entityName>
                    <filter>
                        <fieldId>id</fieldId>
                        <operator>EQUALS</operator>
                        <value>{username}</value>
                    </filter>
                </query>
                ]]>
             </ser:xmlDoc>
          </ser:genericInvoke>
       </soapenv:Body>
    </soapenv:Envelope>"""

    auth_str = f"{username}:{password}"
    b64_auth = base64.b64encode(auth_str.encode()).decode()
    
    headers = {
        "Authorization": f"Basic {b64_auth}",
        "Content-Type": "text/xml;charset=UTF-8",
        "SOAPAction": ""
    }

    try:
        # Timeout curto para não travar a API
        response = requests.post(url, data=xml_payload, headers=headers, timeout=10)
        
        # Se der 200, logou. Se der 500 com erro de credencial, falhou.
        if response.status_code == 200:
            if "Credential Authentication Failed" in response.text:
                return False
            return True
        return False
    except:
        return False