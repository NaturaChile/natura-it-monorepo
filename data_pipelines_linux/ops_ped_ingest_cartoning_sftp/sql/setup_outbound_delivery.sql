-- =============================================
-- TABLAS Y PROCEDIMIENTOS PARA OUTBOUND DELIVERY (SAP IDoc)
-- Mensaje: SHP_OBDLV_SAVE_REPLICA
-- =============================================

USE OPS_OrquestaFact;
GO

-- =============================================
-- STAGING: Cabecera de Entregas
-- =============================================
IF OBJECT_ID('Staging_EWM_OutboundDelivery_Header', 'U') IS NOT NULL
    DROP TABLE Staging_EWM_OutboundDelivery_Header;
GO

CREATE TABLE Staging_EWM_OutboundDelivery_Header (
    ID INT IDENTITY(1,1) PRIMARY KEY,
    Delivery_ID NVARCHAR(50) NOT NULL,
    Peso_Bruto DECIMAL(18,3) NULL,
    Volumen DECIMAL(18,3) NULL,
    Destinatario NVARCHAR(255) NULL,
    Direccion NVARCHAR(500) NULL,
    Region NVARCHAR(100) NULL,
    Transportista NVARCHAR(255) NULL,
    Fecha_Entrega NVARCHAR(50) NULL,
    NombreArchivo NVARCHAR(500) NULL,
    FechaCreacion DATETIME DEFAULT GETDATE()
);

CREATE NONCLUSTERED INDEX IX_Staging_OutboundDelivery_Header_DeliveryID 
ON Staging_EWM_OutboundDelivery_Header(Delivery_ID);
GO

-- =============================================
-- STAGING: Detalle de Items
-- =============================================
IF OBJECT_ID('Staging_EWM_OutboundDelivery_Items', 'U') IS NOT NULL
    DROP TABLE Staging_EWM_OutboundDelivery_Items;
GO

CREATE TABLE Staging_EWM_OutboundDelivery_Items (
    ID INT IDENTITY(1,1) PRIMARY KEY,
    Delivery_ID_FK NVARCHAR(50) NOT NULL,
    Item_Number NVARCHAR(50) NULL,
    Material_SKU NVARCHAR(100) NULL,
    Descripcion NVARCHAR(500) NULL,
    Cantidad DECIMAL(18,3) NULL,
    Unidad_Medida NVARCHAR(10) NULL,
    Peso_Neto_Item DECIMAL(18,3) NULL,
    NombreArchivo NVARCHAR(500) NULL,
    FechaCreacion DATETIME DEFAULT GETDATE()
);

CREATE NONCLUSTERED INDEX IX_Staging_OutboundDelivery_Items_DeliveryID 
ON Staging_EWM_OutboundDelivery_Items(Delivery_ID_FK);
GO

-- =============================================
-- TABLA FINAL: Cabecera de Entregas (con versionado)
-- =============================================
IF OBJECT_ID('EWM_OutboundDelivery_Header', 'U') IS NOT NULL
    DROP TABLE EWM_OutboundDelivery_Header;
GO

CREATE TABLE EWM_OutboundDelivery_Header (
    ID INT IDENTITY(1,1) PRIMARY KEY,
    Delivery_ID NVARCHAR(50) NOT NULL,
    Peso_Bruto DECIMAL(18,3) NULL,
    Volumen DECIMAL(18,3) NULL,
    Destinatario NVARCHAR(255) NULL,
    Direccion NVARCHAR(500) NULL,
    Region NVARCHAR(100) NULL,
    Transportista NVARCHAR(255) NULL,
    Fecha_Entrega DATE NULL,  -- Convertida de string
    NumeroVersion INT NOT NULL,
    FechaProceso DATETIME DEFAULT GETDATE(),
    NombreArchivo NVARCHAR(500) NULL
);

CREATE NONCLUSTERED INDEX IX_EWM_OutboundDelivery_Header_DeliveryID 
ON EWM_OutboundDelivery_Header(Delivery_ID);

CREATE NONCLUSTERED INDEX IX_EWM_OutboundDelivery_Header_Version 
ON EWM_OutboundDelivery_Header(NumeroVersion DESC);
GO

-- =============================================
-- TABLA FINAL: Detalle de Items (con versionado)
-- =============================================
IF OBJECT_ID('EWM_OutboundDelivery_Items', 'U') IS NOT NULL
    DROP TABLE EWM_OutboundDelivery_Items;
GO

CREATE TABLE EWM_OutboundDelivery_Items (
    ID INT IDENTITY(1,1) PRIMARY KEY,
    Delivery_ID_FK NVARCHAR(50) NOT NULL,
    Item_Number NVARCHAR(50) NULL,
    Material_SKU NVARCHAR(100) NULL,
    Descripcion NVARCHAR(500) NULL,
    Cantidad DECIMAL(18,3) NULL,
    Unidad_Medida NVARCHAR(10) NULL,
    Peso_Neto_Item DECIMAL(18,3) NULL,
    NumeroVersion INT NOT NULL,
    FechaProceso DATETIME DEFAULT GETDATE(),
    NombreArchivo NVARCHAR(500) NULL
);

CREATE NONCLUSTERED INDEX IX_EWM_OutboundDelivery_Items_DeliveryID 
ON EWM_OutboundDelivery_Items(Delivery_ID_FK);

CREATE NONCLUSTERED INDEX IX_EWM_OutboundDelivery_Items_Version 
ON EWM_OutboundDelivery_Items(NumeroVersion DESC);
GO

-- =============================================
-- STORED PROCEDURE: Procesar Outbound Delivery
-- =============================================
IF OBJECT_ID('sp_Procesar_OutboundDelivery_EWM', 'P') IS NOT NULL
    DROP PROCEDURE sp_Procesar_OutboundDelivery_EWM;
GO

CREATE PROCEDURE sp_Procesar_OutboundDelivery_EWM
    @NombreArchivo NVARCHAR(500)
AS
BEGIN
    SET NOCOUNT ON;
    
    DECLARE @NumeroVersion INT;
    DECLARE @RegistrosHeader INT = 0;
    DECLARE @RegistrosItems INT = 0;
    
    BEGIN TRY
        BEGIN TRANSACTION;
        
        -- 1. Determinar número de versión
        SELECT @NumeroVersion = ISNULL(MAX(NumeroVersion), 0) + 1
        FROM EWM_OutboundDelivery_Header;
        
        -- 2. Limpiar datos y transformar fecha
        -- Insertar HEADERS
        INSERT INTO EWM_OutboundDelivery_Header (
            Delivery_ID, Peso_Bruto, Volumen, Destinatario, Direccion, 
            Region, Transportista, Fecha_Entrega, NumeroVersion, NombreArchivo
        )
        SELECT 
            LTRIM(RTRIM(Delivery_ID)),
            NULLIF(Peso_Bruto, 0),
            NULLIF(Volumen, 0),
            LTRIM(RTRIM(Destinatario)),
            LTRIM(RTRIM(Direccion)),
            LTRIM(RTRIM(Region)),
            LTRIM(RTRIM(Transportista)),
            -- Convertir fecha de formato YYYYMMDD a DATE
            TRY_CONVERT(DATE, Fecha_Entrega, 112),
            @NumeroVersion,
            @NombreArchivo
        FROM Staging_EWM_OutboundDelivery_Header
        WHERE NombreArchivo = @NombreArchivo
          AND LTRIM(RTRIM(Delivery_ID)) <> '';
        
        SET @RegistrosHeader = @@ROWCOUNT;
        
        -- 3. Insertar ITEMS
        INSERT INTO EWM_OutboundDelivery_Items (
            Delivery_ID_FK, Item_Number, Material_SKU, Descripcion,
            Cantidad, Unidad_Medida, Peso_Neto_Item, NumeroVersion, NombreArchivo
        )
        SELECT 
            LTRIM(RTRIM(Delivery_ID_FK)),
            LTRIM(RTRIM(Item_Number)),
            LTRIM(RTRIM(Material_SKU)),
            LTRIM(RTRIM(Descripcion)),
            NULLIF(Cantidad, 0),
            LTRIM(RTRIM(Unidad_Medida)),
            NULLIF(Peso_Neto_Item, 0),
            @NumeroVersion,
            @NombreArchivo
        FROM Staging_EWM_OutboundDelivery_Items
        WHERE NombreArchivo = @NombreArchivo
          AND LTRIM(RTRIM(Delivery_ID_FK)) <> '';
        
        SET @RegistrosItems = @@ROWCOUNT;
        
        -- 4. Registrar en bitácora
        INSERT INTO BitacoraArchivos (NombreArchivo, Estado, Mensaje)
        VALUES (
            @NombreArchivo, 
            'Procesado', 
            'Headers: ' + CAST(@RegistrosHeader AS NVARCHAR) + ' | Items: ' + CAST(@RegistrosItems AS NVARCHAR) + ' | Version: ' + CAST(@NumeroVersion AS NVARCHAR)
        );
        
        -- 5. Limpiar staging
        DELETE FROM Staging_EWM_OutboundDelivery_Header WHERE NombreArchivo = @NombreArchivo;
        DELETE FROM Staging_EWM_OutboundDelivery_Items WHERE NombreArchivo = @NombreArchivo;
        
        COMMIT TRANSACTION;
        
        PRINT 'Procesado exitosamente: ' + @NombreArchivo;
        PRINT 'Headers: ' + CAST(@RegistrosHeader AS NVARCHAR) + ' | Items: ' + CAST(@RegistrosItems AS NVARCHAR);
        PRINT 'Version: ' + CAST(@NumeroVersion AS NVARCHAR);
        
    END TRY
    BEGIN CATCH
        IF @@TRANCOUNT > 0
            ROLLBACK TRANSACTION;
        
        DECLARE @ErrorMsg NVARCHAR(4000) = ERROR_MESSAGE();
        RAISERROR(@ErrorMsg, 16, 1);
    END CATCH
END;
GO

PRINT 'Estructura de Outbound Delivery creada exitosamente';
PRINT 'Tablas: Staging_EWM_OutboundDelivery_Header, Staging_EWM_OutboundDelivery_Items';
PRINT 'Tablas: EWM_OutboundDelivery_Header, EWM_OutboundDelivery_Items';
PRINT 'SP: sp_Procesar_OutboundDelivery_EWM';
