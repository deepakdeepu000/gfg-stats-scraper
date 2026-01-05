def get_custom_docs_html():
    """
    Returns Swagger UI HTML configured to highlight dedicated 
    schemas and examples for each GeeksforGeeks API endpoint.
    """
    return """
    <!DOCTYPE html>
    <html>
    <head>
    <link type="text/css" rel="stylesheet" href="https://cdn.jsdelivr.net/npm/swagger-ui-dist@5/swagger-ui.css">
    <link rel="shortcut icon" href="https://fastapi.tiangolo.com/img/favicon.png">
    <title>GFG Scraper API - Detailed Documentation</title>
    <style>
        body { margin: 0; padding: 0; background-color: #f8f9fa; }
        .swagger-ui .topbar { display: none; }
        /* Highlighting the example/schema area */
        .swagger-ui .model-example { background: #1b1b1b; padding: 10px; border-radius: 4px; }
    </style>
    </head>
    <body>
    <div id="swagger-ui"></div>
    <script src="https://cdn.jsdelivr.net/npm/swagger-ui-dist@5/swagger-ui-bundle.js"></script>
    <script src="https://cdn.jsdelivr.net/npm/swagger-ui-dist@5/swagger-ui-standalone-preset.js"></script>
    <script>
        window.onload = () => {
            window.ui = SwaggerUIBundle({
                url: '/openapi.json',
                dom_id: '#swagger-ui',
                presets: [
                    SwaggerUIBundle.presets.apis,
                    SwaggerUIStandalonePreset
                ],
                layout: "BaseLayout",
                deepLinking: true,
                /* Ensures schemas and examples are expanded by default */
                defaultModelExpandDepth: 5,
                defaultModelsExpandDepth: 5,
                docExpansion: 'list',
                showExtensions: true,
                filter: true
            });
        };
    </script>
    </body>
    </html>
    """
