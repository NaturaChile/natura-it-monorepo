USE OPS_OrquestaFact;
GO

-- =============================================
-- 1. TABLAS DE SOPORTE Y STAGING
-- =============================================

-- Bitácora de ejecución (Indispensable para el bot)
IF OBJECT_ID('dbo.BitacoraArchivos', 'U') IS NULL
BEGIN
    CREATE TABLE dbo.BitacoraArchivos(
        Id INT IDENTITY(1,1) PRIMARY KEY,
        NombreArchivo VARCHAR(255) NOT NULL,
        Estado VARCHAR(50),
        Mensaje VARCHAR(MAX),
        FechaEvento DATETIME DEFAULT GETDATE()
    );
END
GO

-- Staging (Donde Python vuelca el CSV crudo)
IF OBJECT_ID('dbo.Staging_EWM_Cartoning', 'U') IS NULL
BEGIN
    CREATE TABLE dbo.Staging_EWM_Cartoning(
        Id BIGINT IDENTITY(1,1) PRIMARY KEY,
        TipoRegistro VARCHAR(50),
        C1 VARCHAR(MAX), -- PedidoID / CajaID
        C2 VARCHAR(MAX), -- Entrega / Posicion
        C3 VARCHAR(MAX), -- TipoCaja / CajaID
        C4 VARCHAR(MAX), -- Vol / SKU
        C5 VARCHAR(MAX), -- Unidad / Descripcion
        C6 VARCHAR(MAX), -- Peso / Cantidad
        C7 VARCHAR(MAX), -- Unidad
        C8 VARCHAR(MAX),
        C9 VARCHAR(MAX),
        C10 VARCHAR(MAX),
        C11 VARCHAR(MAX), -- Tracking
        C12 VARCHAR(MAX),
        C13 VARCHAR(MAX), -- Bultos
        C14 VARCHAR(MAX), -- Cliente
        NombreArchivo VARCHAR(255),
        FechaIngesta DATETIME DEFAULT GETDATE()
    );
END
GO

-- Staging para WaveConfirm
IF OBJECT_ID('dbo.Staging_EWM_WaveConfirm', 'U') IS NULL
BEGIN
    CREATE TABLE dbo.Staging_EWM_WaveConfirm(
        Id BIGINT IDENTITY(1,1) PRIMARY KEY,
        WaveID VARCHAR(50),
        PedidoID VARCHAR(50),
        columna0 VARCHAR(50),
        CajaID VARCHAR(100),
        NombreArchivo VARCHAR(255),
        FechaIngesta DATETIME DEFAULT GETDATE(),
        Procesado BIT DEFAULT 0
    );
    
    CREATE INDEX IX_WaveConfirm_Procesado ON dbo.Staging_EWM_WaveConfirm(Procesado, FechaIngesta);
    CREATE INDEX IX_WaveConfirm_Archivo ON dbo.Staging_EWM_WaveConfirm(NombreArchivo);
    CREATE INDEX IX_WaveConfirm_WaveID ON dbo.Staging_EWM_WaveConfirm(WaveID);
END
GO

-- Staging para OutboundDelivery Header
IF OBJECT_ID('dbo.Staging_EWM_OutboundDelivery_Header', 'U') IS NULL
BEGIN
    CREATE TABLE dbo.Staging_EWM_OutboundDelivery_Header (
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
    ON dbo.Staging_EWM_OutboundDelivery_Header(Delivery_ID);
END
GO

-- Staging para OutboundDelivery Items
IF OBJECT_ID('dbo.Staging_EWM_OutboundDelivery_Items', 'U') IS NULL
BEGIN
    CREATE TABLE dbo.Staging_EWM_OutboundDelivery_Items (
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
    ON dbo.Staging_EWM_OutboundDelivery_Items(Delivery_ID_FK);
END
GO

-- =============================================
-- 2. TABLAS DEL MODELO DE NEGOCIO (Con versionado)
-- =============================================

-- Tabla de PEDIDOS (Con versionado)
IF OBJECT_ID('dbo.EWM_Pedidos', 'U') IS NULL
BEGIN
    CREATE TABLE dbo.EWM_Pedidos(
        Id BIGINT IDENTITY(1,1) PRIMARY KEY,
        PedidoID VARCHAR(100),
        EntregaSAP VARCHAR(100),
        VolumenTotal DECIMAL(18,3),
        UnidadVol VARCHAR(20),
        PesoTotal DECIMAL(18,3),
        UnidadPeso VARCHAR(20),
        TotalBultos INT,
        ClienteID VARCHAR(100),
        NombreArchivo VARCHAR(255),
        NumeroVersion INT DEFAULT 1,
        FechaProceso DATETIME DEFAULT GETDATE()
    );
    -- Índice para búsquedas rápidas de versión
    CREATE INDEX IX_EWM_Pedidos_ID ON dbo.EWM_Pedidos(PedidoID);
END
GO

-- Tabla de CAJAS
IF OBJECT_ID('dbo.EWM_Cajas', 'U') IS NULL
BEGIN
    CREATE TABLE dbo.EWM_Cajas(
        Id BIGINT IDENTITY(1,1) PRIMARY KEY,
        CajaID VARCHAR(100),
        PedidoID VARCHAR(100),
        TipoCaja VARCHAR(50),
        Volumen DECIMAL(18,3),
        Peso DECIMAL(18,3),
        TrackingCode VARCHAR(100),
        NombreArchivo VARCHAR(255),
        NumeroVersion INT,
        FechaProceso DATETIME DEFAULT GETDATE()
    );
END
GO

-- Tabla de ITEMS
IF OBJECT_ID('dbo.EWM_Items', 'U') IS NULL
BEGIN
    CREATE TABLE dbo.EWM_Items(
        Id BIGINT IDENTITY(1,1) PRIMARY KEY,
        PedidoID VARCHAR(100),
        Posicion VARCHAR(50),
        CajaID VARCHAR(100),
        SKU VARCHAR(100),
        Descripcion VARCHAR(MAX),
        Cantidad DECIMAL(18,3),
        Unidad VARCHAR(20),
        NombreArchivo VARCHAR(255),
        NumeroVersion INT,
        FechaProceso DATETIME DEFAULT GETDATE()
    );
END
GO

-- Tabla final de WaveConfirm (Con versionado)
IF OBJECT_ID('dbo.EWM_WaveConfirm', 'U') IS NULL
BEGIN
    CREATE TABLE dbo.EWM_WaveConfirm(
        Id BIGINT IDENTITY(1,1) PRIMARY KEY,
        WaveID VARCHAR(50),
        PedidoID VARCHAR(50),
        CajaID VARCHAR(100),
        NombreArchivo VARCHAR(255),
        NumeroVersion INT DEFAULT 1,
        FechaProceso DATETIME DEFAULT GETDATE()
    );
    -- Índices para búsquedas rápidas de versión y consultas
    CREATE INDEX IX_WaveConfirm_WaveID ON dbo.EWM_WaveConfirm(WaveID);
    CREATE INDEX IX_WaveConfirm_PedidoID ON dbo.EWM_WaveConfirm(PedidoID);
    CREATE INDEX IX_WaveConfirm_CajaID ON dbo.EWM_WaveConfirm(CajaID);
    CREATE INDEX IX_WaveConfirm_Composite ON dbo.EWM_WaveConfirm(WaveID, PedidoID, CajaID);
END
GO

-- Tabla final OutboundDelivery Header (Con versionado)
IF OBJECT_ID('dbo.EWM_OutboundDelivery_Header', 'U') IS NULL
BEGIN
    CREATE TABLE dbo.EWM_OutboundDelivery_Header (
        ID INT IDENTITY(1,1) PRIMARY KEY,
        Delivery_ID NVARCHAR(50) NOT NULL,
        Peso_Bruto DECIMAL(18,3) NULL,
        Volumen DECIMAL(18,3) NULL,
        Destinatario NVARCHAR(255) NULL,
        Direccion NVARCHAR(500) NULL,
        Region NVARCHAR(100) NULL,
        Transportista NVARCHAR(255) NULL,
        Fecha_Entrega DATE NULL,
        NumeroVersion INT NOT NULL,
        FechaProceso DATETIME DEFAULT GETDATE(),
        NombreArchivo NVARCHAR(500) NULL
    );
    
    CREATE NONCLUSTERED INDEX IX_EWM_OutboundDelivery_Header_DeliveryID 
    ON dbo.EWM_OutboundDelivery_Header(Delivery_ID);
    
    CREATE NONCLUSTERED INDEX IX_EWM_OutboundDelivery_Header_Version 
    ON dbo.EWM_OutboundDelivery_Header(NumeroVersion DESC);
END
GO

-- Tabla final OutboundDelivery Items (Con versionado)
IF OBJECT_ID('dbo.EWM_OutboundDelivery_Items', 'U') IS NULL
BEGIN
    CREATE TABLE dbo.EWM_OutboundDelivery_Items (
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
    ON dbo.EWM_OutboundDelivery_Items(Delivery_ID_FK);
    
    CREATE NONCLUSTERED INDEX IX_EWM_OutboundDelivery_Items_Version 
    ON dbo.EWM_OutboundDelivery_Items(NumeroVersion DESC);
END
GO

-- =============================================
-- 3. STORED PROCEDURES
-- =============================================

-- =====================================================
-- SP PARA CARTONING (Con versionado)
-- =====================================================
CREATE OR ALTER PROCEDURE [dbo].[sp_Procesar_Cartoning_EWM]
    @ArchivoActual NVARCHAR(255)
AS
BEGIN
    SET NOCOUNT ON;
    
    BEGIN TRY
        BEGIN TRANSACTION;

        -- 1. Capturamos Pedidos desde Staging_EWM_Cartoning
        SELECT DISTINCT
            C1 AS PedidoID, C2 AS EntregaSAP, 
            TRY_CAST(C4 AS DECIMAL(18,3)) AS Volumen, 
            C5 AS UnidadVol,
            TRY_CAST(C6 AS DECIMAL(18,3)) AS Peso, 
            C7 AS UnidadPeso, 
            TRY_CAST(C13 AS INT) AS Bultos, 
            C14 AS Cliente, 
            NombreArchivo
        INTO #TempPedidos
        FROM Staging_EWM_Cartoning
        WHERE NombreArchivo = @ArchivoActual 
          AND TipoRegistro = 'ZSIEWM_CARTONIZACAO_PEDIDO';

        -- 2. Insertamos Pedidos (Logica +1 Version)
        INSERT INTO EWM_Pedidos (
            PedidoID, EntregaSAP, VolumenTotal, UnidadVol, PesoTotal, UnidadPeso, 
            TotalBultos, ClienteID, NombreArchivo, NumeroVersion
        )
        SELECT 
            T.PedidoID, T.EntregaSAP, T.Volumen, T.UnidadVol, T.Peso, T.UnidadPeso, 
            T.Bultos, T.Cliente, T.NombreArchivo,
            ISNULL((SELECT MAX(NumeroVersion) FROM EWM_Pedidos WHERE PedidoID = T.PedidoID), 0) + 1
        FROM #TempPedidos T;

        -- 3. Insertamos Cajas
        INSERT INTO EWM_Cajas (
            CajaID, PedidoID, TipoCaja, Volumen, Peso, TrackingCode, 
            NombreArchivo, NumeroVersion
        )
        SELECT DISTINCT
            R.C2, R.C1, R.C3, 
            TRY_CAST(R.C4 AS DECIMAL(18,3)), 
            TRY_CAST(R.C6 AS DECIMAL(18,3)), 
            R.C11, R.NombreArchivo,
            (SELECT MAX(NumeroVersion) FROM EWM_Pedidos WHERE PedidoID = R.C1)
        FROM Staging_EWM_Cartoning R
        WHERE R.NombreArchivo = @ArchivoActual 
          AND R.TipoRegistro = 'ZSIEWM_CARTONIZACAO_CAIXA';

        -- 4. Insertamos Items
        INSERT INTO EWM_Items (
            PedidoID, Posicion, CajaID, SKU, Descripcion, 
            Cantidad, Unidad, NombreArchivo, NumeroVersion
        )
        SELECT 
            R.C1, R.C2, R.C3, R.C4, R.C5, 
            TRY_CAST(R.C6 AS DECIMAL(18,3)), R.C7, 
            R.NombreArchivo,
            (SELECT MAX(NumeroVersion) FROM EWM_Pedidos WHERE PedidoID = R.C1)
        FROM Staging_EWM_Cartoning R
        WHERE R.NombreArchivo = @ArchivoActual 
          AND R.TipoRegistro = 'ZSIEWM_CARTONIZACAO_ITEM';

        -- 5. Limpieza y Bitácora
        DROP TABLE IF EXISTS #TempPedidos;
        
        -- Borrar del staging
        DELETE FROM Staging_EWM_Cartoning WHERE NombreArchivo = @ArchivoActual;

        -- Registrar en BitacoraArchivos que terminamos bien
        INSERT INTO BitacoraArchivos (NombreArchivo, Estado, Mensaje)
        VALUES (@ArchivoActual, 'PROCESADO', 'Carga exitosa con versionado.');

        COMMIT TRANSACTION;
        PRINT '--> [VERSIONADO] Archivo procesado y registrado en Bitácora: ' + @ArchivoActual;
        
    END TRY
    BEGIN CATCH
        IF @@TRANCOUNT > 0 ROLLBACK TRANSACTION;
        
        -- Registrar error en Bitácora
        INSERT INTO BitacoraArchivos (NombreArchivo, Estado, Mensaje)
        VALUES (@ArchivoActual, 'ERROR', ERROR_MESSAGE());

        PRINT 'ERROR CRITICO: ' + ERROR_MESSAGE();
    END CATCH
END
GO

-- =====================================================
-- SP PARA WAVECONFIRM (Con versionado)
-- =====================================================
CREATE OR ALTER PROCEDURE sp_Procesar_WaveConfirm_EWM
    @ArchivoActual VARCHAR(255)
AS
BEGIN
    SET NOCOUNT ON;
    
    BEGIN TRY
        BEGIN TRANSACTION;
        
        DECLARE @TotalRegistros INT;
        SELECT @TotalRegistros = COUNT(*) 
        FROM Staging_EWM_WaveConfirm 
        WHERE NombreArchivo = @ArchivoActual AND Procesado = 0;
        
        PRINT '--> Iniciando procesamiento WaveConfirm: ' + @ArchivoActual;
        PRINT '    Total registros staging: ' + CAST(@TotalRegistros AS VARCHAR(10));
        
        -- =====================================================
        -- 1. LIMPIEZA Y VALIDACIÓN DE DATOS
        -- =====================================================
        -- Eliminar registros con datos incompletos/inválidos
        DELETE FROM Staging_EWM_WaveConfirm
        WHERE NombreArchivo = @ArchivoActual 
          AND Procesado = 0
          AND (
              WaveID IS NULL OR LTRIM(RTRIM(WaveID)) = '' OR
              PedidoID IS NULL OR LTRIM(RTRIM(PedidoID)) = '' OR
              CajaID IS NULL OR LTRIM(RTRIM(CajaID)) = ''
          );
        
        DECLARE @Descartados INT = @@ROWCOUNT;
        IF @Descartados > 0
            PRINT '    Registros descartados por datos inválidos: ' + CAST(@Descartados AS VARCHAR(10));
        
        -- Limpiar espacios en blanco
        UPDATE Staging_EWM_WaveConfirm
        SET WaveID = LTRIM(RTRIM(WaveID)),
            PedidoID = LTRIM(RTRIM(PedidoID)),
            CajaID = LTRIM(RTRIM(CajaID))
        WHERE NombreArchivo = @ArchivoActual AND Procesado = 0;
        
        -- =====================================================
        -- 2. CREAR TABLA TEMPORAL PARA VERSIONADO
        -- =====================================================
        CREATE TABLE #TempWaveConfirm (
            WaveID VARCHAR(50),
            PedidoID VARCHAR(50),
            CajaID VARCHAR(100),
            NombreArchivo VARCHAR(255),
            VersionAnterior INT
        );
        
        -- Cargar datos con versión anterior (si existe)
        INSERT INTO #TempWaveConfirm (WaveID, PedidoID, CajaID, NombreArchivo, VersionAnterior)
        SELECT 
            s.WaveID,
            s.PedidoID,
            s.CajaID,
            s.NombreArchivo,
            ISNULL(
                (SELECT MAX(NumeroVersion) 
                 FROM EWM_WaveConfirm 
                 WHERE WaveID = s.WaveID 
                   AND PedidoID = s.PedidoID 
                   AND CajaID = s.CajaID), 
                0
            ) AS VersionAnterior
        FROM Staging_EWM_WaveConfirm s
        WHERE s.NombreArchivo = @ArchivoActual AND s.Procesado = 0;
        
        DECLARE @Procesados INT = @@ROWCOUNT;
        PRINT '    Registros válidos a procesar: ' + CAST(@Procesados AS VARCHAR(10));
        
        -- =====================================================
        -- 3. INSERTAR EN TABLA FINAL CON VERSIONADO
        -- =====================================================
        -- Detectar registros nuevos vs actualizaciones
        DECLARE @Nuevos INT, @Actualizaciones INT;
        
        SELECT @Nuevos = COUNT(*) FROM #TempWaveConfirm WHERE VersionAnterior = 0;
        SELECT @Actualizaciones = COUNT(*) FROM #TempWaveConfirm WHERE VersionAnterior > 0;
        
        PRINT '    Registros nuevos: ' + CAST(@Nuevos AS VARCHAR(10));
        PRINT '    Actualizaciones (nuevas versiones): ' + CAST(@Actualizaciones AS VARCHAR(10));
        
        -- Insertar todos con versionado automático
        INSERT INTO EWM_WaveConfirm (WaveID, PedidoID, CajaID, NombreArchivo, NumeroVersion, FechaProceso)
        SELECT 
            WaveID,
            PedidoID,
            CajaID,
            NombreArchivo,
            VersionAnterior + 1 AS NumeroVersion,  -- Incrementar versión
            GETDATE() AS FechaProceso
        FROM #TempWaveConfirm;
        
        DECLARE @Insertados INT = @@ROWCOUNT;
        PRINT '    Total insertado en EWM_WaveConfirm: ' + CAST(@Insertados AS VARCHAR(10));
        
        -- =====================================================
        -- 4. MARCAR STAGING COMO PROCESADO
        -- =====================================================
        UPDATE Staging_EWM_WaveConfirm
        SET Procesado = 1
        WHERE NombreArchivo = @ArchivoActual;
        
        -- =====================================================
        -- 5. LIMPIEZA Y BITÁCORA
        -- =====================================================
        DROP TABLE IF EXISTS #TempWaveConfirm;
        
        -- Borrar del staging
        DELETE FROM Staging_EWM_WaveConfirm WHERE NombreArchivo = @ArchivoActual;
        
        -- Registrar en bitácora
        INSERT INTO BitacoraArchivos (NombreArchivo, Estado, Mensaje)
        VALUES (
            @ArchivoActual, 
            'PROCESADO', 
            'WaveConfirm procesado con versionado: ' + 
            CAST(@Nuevos AS VARCHAR(10)) + ' nuevos, ' + 
            CAST(@Actualizaciones AS VARCHAR(10)) + ' actualizaciones'
        );
        
        COMMIT TRANSACTION;
        PRINT '--> [VERSIONADO] WaveConfirm procesado y registrado en Bitácora: ' + @ArchivoActual;
        
    END TRY
    BEGIN CATCH
        IF @@TRANCOUNT > 0
            ROLLBACK TRANSACTION;
        
        -- Limpiar tablas temporales en caso de error
        DROP TABLE IF EXISTS #TempWaveConfirm;
            
        DECLARE @ErrorMessage NVARCHAR(4000) = ERROR_MESSAGE();
        
        -- Registrar error en bitácora
        INSERT INTO BitacoraArchivos (NombreArchivo, Estado, Mensaje)
        VALUES (@ArchivoActual, 'ERROR', 'WaveConfirm: ' + @ErrorMessage);
        
        PRINT 'ERROR CRITICO: ' + @ErrorMessage;
        RAISERROR(@ErrorMessage, 16, 1);
    END CATCH
END
GO

-- =====================================================
-- SP PARA OUTBOUND DELIVERY (Con versionado)
-- =====================================================
CREATE OR ALTER PROCEDURE sp_Procesar_OutboundDelivery_EWM
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
            'PROCESADO', 
            'OutboundDelivery - Headers: ' + CAST(@RegistrosHeader AS NVARCHAR) + ' | Items: ' + CAST(@RegistrosItems AS NVARCHAR) + ' | Version: ' + CAST(@NumeroVersion AS NVARCHAR)
        );
        
        -- 5. Limpiar staging
        DELETE FROM Staging_EWM_OutboundDelivery_Header WHERE NombreArchivo = @NombreArchivo;
        DELETE FROM Staging_EWM_OutboundDelivery_Items WHERE NombreArchivo = @NombreArchivo;
        
        COMMIT TRANSACTION;
        
        PRINT '--> [VERSIONADO] OutboundDelivery procesado: ' + @NombreArchivo;
        PRINT '    Headers: ' + CAST(@RegistrosHeader AS NVARCHAR) + ' | Items: ' + CAST(@RegistrosItems AS NVARCHAR);
        PRINT '    Version: ' + CAST(@NumeroVersion AS NVARCHAR);
        
    END TRY
    BEGIN CATCH
        IF @@TRANCOUNT > 0
            ROLLBACK TRANSACTION;
        
        DECLARE @ErrorMsg NVARCHAR(4000) = ERROR_MESSAGE();
        
        -- Registrar error en bitácora
        INSERT INTO BitacoraArchivos (NombreArchivo, Estado, Mensaje)
        VALUES (@NombreArchivo, 'ERROR', 'OutboundDelivery: ' + @ErrorMsg);
        
        PRINT 'ERROR CRITICO: ' + @ErrorMsg;
        RAISERROR(@ErrorMsg, 16, 1);
    END CATCH
END;
GO

PRINT '=============================================';
PRINT 'SCHEMA COMPLETO CREADO EXITOSAMENTE';
PRINT '=============================================';
PRINT '';
PRINT 'TABLAS DE STAGING (5):';
PRINT '  - BitacoraArchivos';
PRINT '  - Staging_EWM_Cartoning';
PRINT '  - Staging_EWM_WaveConfirm';
PRINT '  - Staging_EWM_OutboundDelivery_Header';
PRINT '  - Staging_EWM_OutboundDelivery_Items';
PRINT '';
PRINT 'TABLAS FINALES (7):';
PRINT '  - EWM_Pedidos (Cartoning)';
PRINT '  - EWM_Cajas (Cartoning)';
PRINT '  - EWM_Items (Cartoning)';
PRINT '  - EWM_WaveConfirm';
PRINT '  - EWM_OutboundDelivery_Header';
PRINT '  - EWM_OutboundDelivery_Items';
PRINT '';
PRINT 'STORED PROCEDURES (3):';
PRINT '  - sp_Procesar_Cartoning_EWM';
PRINT '  - sp_Procesar_WaveConfirm_EWM';
PRINT '  - sp_Procesar_OutboundDelivery_EWM';
PRINT '';
PRINT 'Todas las tablas incluyen versionado automatico';
PRINT '=============================================';
