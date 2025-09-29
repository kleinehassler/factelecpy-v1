-- Base de Datos para Facturación Electrónica Ecuador - SRI
-- Esquema versión 2.0.0

CREATE DATABASE IF NOT EXISTS facturacion_electronica;
USE facturacion_electronica;

-- Tabla de Empresas
CREATE TABLE empresas (
    id INT PRIMARY KEY AUTO_INCREMENT,
    ruc VARCHAR(13) NOT NULL UNIQUE,
    razon_social VARCHAR(300) NOT NULL,
    nombre_comercial VARCHAR(300),
    direccion_matriz VARCHAR(300) NOT NULL,
    telefono VARCHAR(20),
    email VARCHAR(100),
    obligado_contabilidad ENUM('SI', 'NO') DEFAULT 'NO',
    contribuyente_especial VARCHAR(10),
    logo_path VARCHAR(255),
    cert_path VARCHAR(255),
    cert_password VARCHAR(255),
    ambiente ENUM('1', '2') DEFAULT '1', -- 1=Pruebas, 2=Producción
    tipo_emision ENUM('1', '2') DEFAULT '1', -- 1=Normal, 2=Contingencia
    activo BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
);

-- Tabla de Establecimientos
CREATE TABLE establecimientos (
    id INT PRIMARY KEY AUTO_INCREMENT,
    empresa_id INT NOT NULL,
    codigo VARCHAR(3) NOT NULL,
    direccion VARCHAR(300) NOT NULL,
    nombre VARCHAR(300),
    telefono VARCHAR(20),
    email VARCHAR(100),
    activo BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (empresa_id) REFERENCES empresas(id),
    UNIQUE KEY uk_empresa_codigo (empresa_id, codigo)
);

-- Tabla de Puntos de Emisión
CREATE TABLE puntos_emision (
    id INT PRIMARY KEY AUTO_INCREMENT,
    establecimiento_id INT NOT NULL,
    codigo VARCHAR(3) NOT NULL,
    descripcion VARCHAR(300),
    activo BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (establecimiento_id) REFERENCES establecimientos(id),
    UNIQUE KEY uk_establecimiento_codigo (establecimiento_id, codigo)
);

-- Tabla de Clientes
CREATE TABLE clientes (
    id INT PRIMARY KEY AUTO_INCREMENT,
    tipo_identificacion ENUM('04', '05', '06', '07', '08') NOT NULL, -- Cédula, RUC, Pasaporte, etc.
    identificacion VARCHAR(20) NOT NULL,
    razon_social VARCHAR(300) NOT NULL,
    direccion VARCHAR(300),
    telefono VARCHAR(20),
    email VARCHAR(100),
    activo BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    UNIQUE KEY uk_tipo_identificacion (tipo_identificacion, identificacion)
);

-- Tabla de Productos/Servicios
CREATE TABLE productos (
    id INT PRIMARY KEY AUTO_INCREMENT,
    codigo_principal VARCHAR(25) NOT NULL,
    codigo_auxiliar VARCHAR(25),
    descripcion VARCHAR(300) NOT NULL,
    precio_unitario DECIMAL(12,6) NOT NULL,
    tipo ENUM('BIEN', 'SERVICIO') DEFAULT 'BIEN',
    codigo_impuesto VARCHAR(2) DEFAULT '2', -- 2=IVA, 3=ICE, etc.
    porcentaje_iva DECIMAL(5,4) DEFAULT 0.12,
    activo BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    UNIQUE KEY uk_codigo_principal (codigo_principal)
);

-- Tabla de Secuencias
CREATE TABLE secuencias (
    id INT PRIMARY KEY AUTO_INCREMENT,
    punto_emision_id INT NOT NULL,
    tipo_comprobante ENUM('01', '03', '04', '05', '06', '07') NOT NULL, -- 01=Factura, 03=Liquidación, etc.
    secuencia_actual INT NOT NULL DEFAULT 0,
    activo BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (punto_emision_id) REFERENCES puntos_emision(id),
    UNIQUE KEY uk_punto_tipo (punto_emision_id, tipo_comprobante)
);

-- Tabla de Facturas (Cabecera)
CREATE TABLE facturas (
    id INT PRIMARY KEY AUTO_INCREMENT,
    empresa_id INT NOT NULL,
    establecimiento_id INT NOT NULL,
    punto_emision_id INT NOT NULL,
    cliente_id INT NOT NULL,
    
    -- Información del comprobante
    tipo_comprobante VARCHAR(2) DEFAULT '01', -- 01=Factura
    numero_comprobante VARCHAR(17) NOT NULL, -- formato: XXX-XXX-XXXXXXXXX
    fecha_emision DATETIME NOT NULL,
    ambiente VARCHAR(1) NOT NULL, -- 1=Pruebas, 2=Producción
    tipo_emision VARCHAR(1) NOT NULL, -- 1=Normal, 2=Contingencia
    clave_acceso VARCHAR(49) NOT NULL UNIQUE,
    
    -- Información tributaria
    subtotal_sin_impuestos DECIMAL(12,2) NOT NULL,
    subtotal_0 DECIMAL(12,2) DEFAULT 0,
    subtotal_12 DECIMAL(12,2) DEFAULT 0,
    subtotal_no_objeto_iva DECIMAL(12,2) DEFAULT 0,
    subtotal_exento_iva DECIMAL(12,2) DEFAULT 0,
    total_descuento DECIMAL(12,2) DEFAULT 0,
    ice DECIMAL(12,2) DEFAULT 0,
    iva_12 DECIMAL(12,2) DEFAULT 0,
    irbpnr DECIMAL(12,2) DEFAULT 0,
    propina DECIMAL(12,2) DEFAULT 0,
    valor_total DECIMAL(12,2) NOT NULL,
    
    -- Información adicional
    moneda VARCHAR(5) DEFAULT 'DOLAR',
    observaciones TEXT,
    
    -- Estados del documento
    estado_sri ENUM('GENERADO', 'FIRMADO', 'AUTORIZADO', 'RECHAZADO', 'DEVUELTO') DEFAULT 'GENERADO',
    numero_autorizacion VARCHAR(49),
    fecha_autorizacion DATETIME,
    
    -- Archivos generados
    xml_path VARCHAR(500),
    xml_firmado_path VARCHAR(500),
    pdf_path VARCHAR(500),
    
    -- Envío por correo
    email_enviado BOOLEAN DEFAULT FALSE,
    fecha_email DATETIME,
    
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    
    FOREIGN KEY (empresa_id) REFERENCES empresas(id),
    FOREIGN KEY (establecimiento_id) REFERENCES establecimientos(id),
    FOREIGN KEY (punto_emision_id) REFERENCES puntos_emision(id),
    FOREIGN KEY (cliente_id) REFERENCES clientes(id),
    
    INDEX idx_numero_comprobante (numero_comprobante),
    INDEX idx_clave_acceso (clave_acceso),
    INDEX idx_fecha_emision (fecha_emision),
    INDEX idx_estado_sri (estado_sri)
);

-- Tabla de Detalles de Factura
CREATE TABLE factura_detalles (
    id INT PRIMARY KEY AUTO_INCREMENT,
    factura_id INT NOT NULL,
    codigo_principal VARCHAR(25) NOT NULL,
    codigo_auxiliar VARCHAR(25),
    descripcion VARCHAR(300) NOT NULL,
    cantidad DECIMAL(12,6) NOT NULL,
    precio_unitario DECIMAL(12,6) NOT NULL,
    descuento DECIMAL(12,2) DEFAULT 0,
    precio_total_sin_impuesto DECIMAL(12,2) NOT NULL,
    
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (factura_id) REFERENCES facturas(id) ON DELETE CASCADE
);

-- Tabla de Impuestos por Detalle
CREATE TABLE factura_detalle_impuestos (
    id INT PRIMARY KEY AUTO_INCREMENT,
    detalle_id INT NOT NULL,
    codigo VARCHAR(2) NOT NULL, -- 2=IVA, 3=ICE, 5=IRBPNR
    codigo_porcentaje VARCHAR(4) NOT NULL, -- 0, 2, 3, 6, 7
    tarifa DECIMAL(5,4) NOT NULL,
    base_imponible DECIMAL(12,2) NOT NULL,
    valor DECIMAL(12,2) NOT NULL,
    
    FOREIGN KEY (detalle_id) REFERENCES factura_detalles(id) ON DELETE CASCADE
);

-- Tabla de Información Adicional
CREATE TABLE factura_info_adicional (
    id INT PRIMARY KEY AUTO_INCREMENT,
    factura_id INT NOT NULL,
    nombre VARCHAR(50) NOT NULL,
    valor VARCHAR(300) NOT NULL,
    
    FOREIGN KEY (factura_id) REFERENCES facturas(id) ON DELETE CASCADE
);

-- Tabla de Proformas (similar a facturas pero sin efectos tributarios)
CREATE TABLE proformas (
    id INT PRIMARY KEY AUTO_INCREMENT,
    empresa_id INT NOT NULL,
    establecimiento_id INT NOT NULL,
    punto_emision_id INT NOT NULL,
    cliente_id INT NOT NULL,
    
    numero_proforma VARCHAR(17) NOT NULL,
    fecha_emision DATETIME NOT NULL,
    fecha_validez DATE,
    
    subtotal_sin_impuestos DECIMAL(12,2) NOT NULL,
    subtotal_0 DECIMAL(12,2) DEFAULT 0,
    subtotal_12 DECIMAL(12,2) DEFAULT 0,
    total_descuento DECIMAL(12,2) DEFAULT 0,
    iva_12 DECIMAL(12,2) DEFAULT 0,
    valor_total DECIMAL(12,2) NOT NULL,
    
    observaciones TEXT,
    estado ENUM('ACTIVA', 'FACTURADA', 'VENCIDA', 'CANCELADA') DEFAULT 'ACTIVA',
    
    pdf_path VARCHAR(500),
    email_enviado BOOLEAN DEFAULT FALSE,
    fecha_email DATETIME,
    
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    
    FOREIGN KEY (empresa_id) REFERENCES empresas(id),
    FOREIGN KEY (establecimiento_id) REFERENCES establecimientos(id),
    FOREIGN KEY (punto_emision_id) REFERENCES puntos_emision(id),
    FOREIGN KEY (cliente_id) REFERENCES clientes(id)
);

-- Tabla de Detalles de Proforma
CREATE TABLE proforma_detalles (
    id INT PRIMARY KEY AUTO_INCREMENT,
    proforma_id INT NOT NULL,
    codigo_principal VARCHAR(25) NOT NULL,
    codigo_auxiliar VARCHAR(25),
    descripcion VARCHAR(300) NOT NULL,
    cantidad DECIMAL(12,6) NOT NULL,
    precio_unitario DECIMAL(12,6) NOT NULL,
    descuento DECIMAL(12,2) DEFAULT 0,
    precio_total_sin_impuesto DECIMAL(12,2) NOT NULL,
    codigo_impuesto VARCHAR(2) DEFAULT '2',
    porcentaje_iva DECIMAL(5,4) DEFAULT 0.12,
    
    FOREIGN KEY (proforma_id) REFERENCES proformas(id) ON DELETE CASCADE
);

-- Tabla de Logs del Sistema
CREATE TABLE logs_sistema (
    id INT PRIMARY KEY AUTO_INCREMENT,
    tipo ENUM('INFO', 'WARNING', 'ERROR', 'DEBUG') NOT NULL,
    modulo VARCHAR(50) NOT NULL,
    mensaje TEXT NOT NULL,
    detalle LONGTEXT DEFAULT NULL;
    usuario VARCHAR(50),
    ip_address VARCHAR(45),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Tabla de Usuarios del Sistema
CREATE TABLE usuarios (
    id INT PRIMARY KEY AUTO_INCREMENT,
    username VARCHAR(50) NOT NULL UNIQUE,
    email VARCHAR(100) NOT NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    nombre VARCHAR(100) NOT NULL,
    apellido VARCHAR(100) NOT NULL,
    activo BOOLEAN DEFAULT TRUE,
    es_admin BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
);

-- Insertar datos de ejemplo
INSERT INTO empresas (ruc, razon_social, nombre_comercial, direccion_matriz, telefono, email, obligado_contabilidad) 
VALUES ('1234567890001', 'EMPRESA DE EJEMPLO S.A.', 'EMPRESA EJEMPLO', 'AV. EJEMPLO 123 Y CALLE PRINCIPAL', '02-2345678', 'info@ejemplo.com', 'SI');

INSERT INTO establecimientos (empresa_id, codigo, direccion, nombre) 
VALUES (1, '001', 'AV. EJEMPLO 123 Y CALLE PRINCIPAL', 'MATRIZ');

INSERT INTO puntos_emision (establecimiento_id, codigo, descripcion) 
VALUES (1, '001', 'CAJA 1');

INSERT INTO secuencias (punto_emision_id, tipo_comprobante, secuencia_actual) 
VALUES (1, '01', 0);

INSERT INTO usuarios (username, email, password_hash, nombre, apellido, es_admin) 
VALUES ('admin', 'admin@ejemplo.com', '$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LewTpCy.t/K7O9OGa', 'Administrador', 'Sistema', TRUE);
-- Password: admin123

-- Crear índices adicionales para mejorar performance
CREATE INDEX idx_facturas_fecha ON facturas(fecha_emision);
CREATE INDEX idx_facturas_cliente ON facturas(cliente_id);
CREATE INDEX idx_facturas_estado ON facturas(estado_sri);
CREATE INDEX idx_clientes_identificacion ON clientes(identificacion);
CREATE INDEX idx_productos_codigo ON productos(codigo_principal);