Propuesta de ACTIVE-IA en modo LIVE con Moodle.

Quiero que en el perfil de cada tutor aparezca una configuracion para guardar las credenciales de moodle (ususario y password).

con esas credenciales el sistema puede hacer peticiones a moodle con el token de moodle, aqui hay un ejemplo para obtener el token de moodle en n8n:

{
  "nodes": [
    {
      "parameters": {
        "method": "POST",
        "url": "={{ $json.moodleHost + \"/login/token.php\" }}",
        "sendBody": true,
        "contentType": "form-urlencoded",
        "bodyParameters": {
          "parameters": [
            {
              "name": "username",
              "value": USUARIO_MOODLE
            },
            {
              "name": "password",
              "value": PASSWORD_MOODLE
            },
            {
              "name": "service",
              "value": "moodle_mobile_app"
            }
          ]
        },
        "options": {}
      },
      "id": "f315babc-671f-4f27-9484-ce624d7fdfeb",
      "name": "Get Token",
      "type": "n8n-nodes-base.httpRequest",
      "typeVersion": 4.4,
      "position": [
        672,
        320
      ],
      "onError": "continueErrorOutput"
    }
  ],
  "connections": {
    "Get Token": {
      "main": [
        []
      ],
      "error": [
        []
      ]
    }
  },
  "pinData": {},
  "meta": {
    "aiBuilderAssisted": true,
    "builderVariant": "mcp",
    "templateCredsSetupCompleted": true,
    "instanceId": "598ec986d25c6df54fb0d078300b3fe17c684a42adb35adae449cd6ffe3d8def"
  }
}

Luego con la api de moodle mobile app, se deberian hacer las peticiones necesarias.

El alcance que yo quiero es el siguiente:

Cada tutor tiene cursos en moodle, puede tener varios cursos, el tutor debe poder ver los trabajos pendientes que tiene por corregir en cada materia, un ejemplo real:

Yo siendo tutor de programacion 1 y programacion 3 tengo comisiones 1,2 y 3 en programacion 1 y comision 7 en programacion 3. 

En cada programacion hay trabajos practicos abiertos que los alumnos pueden entregar a lo largo del cursado sin fecha limite, por ejemplo en Programacion 1 hay 10 trabajos practicos, 1 por cada unidad, pero ademas hay examenes parciales, recuperatorios de parciales, extensiones de parciales, examenes globales y finales. Entonces como tutor yo debo estar muy atento de las entregas que me hacen, este sistema viene a arreglar eso, que el tutor no tenga que meterse manualmente a todos los trabajos a ver si hay entregas. Este sistema lo que va a hacer es reflejarle en el dashboard al tutor las entregas pendientes con link directo para ir a descargar la entrega, subirla activia para que la corrija y pueda entregar la correccion al alumno.

Todo el diseño ya esta pensado y esta en la carpeta `design_handoff_pendientes_moodle` en este diseño faltaria agregar la division por materia

