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
        ID BIGINT IDENTITY(1,1) PRIMARY KEY,
        TipoRegistro NVARCHAR(50), -- debe soportar valores como ZSIEWM_CARTONIZACAO_*
        C1 NVARCHAR(510),
        C2 NVARCHAR(510),
        C3 NVARCHAR(510),
        C4 NVARCHAR(510),
        C5 NVARCHAR(510),
        C6 NVARCHAR(510),
        C7 NVARCHAR(510),
        C8 NVARCHAR(510),
        C9 NVARCHAR(510),
        C10 NVARCHAR(510),
        C11 NVARCHAR(510),
        C12 NVARCHAR(510),
        C13 NVARCHAR(510),
        C14 NVARCHAR(510),
        NombreArchivo NVARCHAR(1000),
        FechaCreacion DATETIME DEFAULT GETDATE()
    );
END
GO

-- Staging para WaveConfirm
IF OBJECT_ID('dbo.Staging_EWM_WaveConfirm', 'U') IS NULL
BEGIN
    CREATE TABLE dbo.Staging_EWM_WaveConfirm(
        ID BIGINT IDENTITY(1,1) PRIMARY KEY,
        WaveID VARCHAR(50),
        PedidoID VARCHAR(50),
        columna0 VARCHAR(50),
        CajaID VARCHAR(100),
        columna_extra VARCHAR(100),
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
        Delivery_ID NVARCHAR(100) NOT NULL,
        Peso_Bruto DECIMAL(18,3) NULL,
        Volumen DECIMAL(18,3) NULL,
        Destinatario NVARCHAR(510) NULL,
        Direccion NVARCHAR(1000) NULL,
        Region NVARCHAR(200) NULL,
        Transportista NVARCHAR(510) NULL,
        Fecha_Entrega NVARCHAR(100) NULL,
        NombreArchivo NVARCHAR(1000) NULL,
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
        Delivery_ID_FK NVARCHAR(100) NOT NULL,
        Item_Number NVARCHAR(100) NULL,
        Material_SKU NVARCHAR(200) NULL,
        Descripcion NVARCHAR(1000) NULL,
        Cantidad DECIMAL(18,3) NULL,
        Unidad_Medida NVARCHAR(20) NULL,
        Peso_Neto_Item DECIMAL(18,3) NULL,
        NombreArchivo NVARCHAR(1000) NULL,
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
        Delivery_ID NVARCHAR(100) NOT NULL,
        Peso_Bruto DECIMAL(18,3) NULL,
        Volumen DECIMAL(18,3) NULL,
        Destinatario NVARCHAR(510) NULL,
        Direccion NVARCHAR(1000) NULL,
        Region NVARCHAR(200) NULL,
        Transportista NVARCHAR(510) NULL,
        Fecha_Entrega DATE NULL,
        NumeroVersion INT NOT NULL,
        FechaProceso DATETIME DEFAULT GETDATE(),
        NombreArchivo NVARCHAR(1000) NULL
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
        Delivery_ID_FK NVARCHAR(100) NOT NULL,
        Item_Number NVARCHAR(100) NULL,
        Material_SKU NVARCHAR(200) NULL,
        Descripcion NVARCHAR(1000) NULL,
        Cantidad DECIMAL(18,3) NULL,
        Unidad_Medida NVARCHAR(20) NULL,
        Peso_Neto_Item DECIMAL(18,3) NULL,
        NumeroVersion INT NOT NULL,
        FechaProceso DATETIME DEFAULT GETDATE(),
        NombreArchivo NVARCHAR(1000) NULL
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
    @ArchivoActual NVARCHAR(500)
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
    @ArchivoActual NVARCHAR(500)
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
    @ArchivoActual NVARCHAR(500)
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
            @ArchivoActual
        FROM Staging_EWM_OutboundDelivery_Header
        WHERE NombreArchivo = @ArchivoActual
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
            @ArchivoActual
        FROM Staging_EWM_OutboundDelivery_Items
        WHERE NombreArchivo = @ArchivoActual
          AND LTRIM(RTRIM(Delivery_ID_FK)) <> '';
        
        SET @RegistrosItems = @@ROWCOUNT;
        
        -- 4. Registrar en bitácora
        INSERT INTO BitacoraArchivos (NombreArchivo, Estado, Mensaje)
        VALUES (
            @ArchivoActual, 
            'PROCESADO', 
            'OutboundDelivery - Headers: ' + CAST(@RegistrosHeader AS NVARCHAR) + ' | Items: ' + CAST(@RegistrosItems AS NVARCHAR) + ' | Version: ' + CAST(@NumeroVersion AS NVARCHAR)
        );
        
        -- 5. Limpiar staging
        DELETE FROM Staging_EWM_OutboundDelivery_Header WHERE NombreArchivo = @ArchivoActual;
        DELETE FROM Staging_EWM_OutboundDelivery_Items WHERE NombreArchivo = @ArchivoActual;
        
        COMMIT TRANSACTION;
        
        PRINT '--> [VERSIONADO] OutboundDelivery procesado: ' + @ArchivoActual;
        PRINT '    Headers: ' + CAST(@RegistrosHeader AS NVARCHAR) + ' | Items: ' + CAST(@RegistrosItems AS NVARCHAR);
        PRINT '    Version: ' + CAST(@NumeroVersion AS NVARCHAR);
        
    END TRY
    BEGIN CATCH
        IF @@TRANCOUNT > 0
            ROLLBACK TRANSACTION;
        
        DECLARE @ErrorMsg NVARCHAR(4000) = ERROR_MESSAGE();
        
        -- Registrar error en bitácora
        INSERT INTO BitacoraArchivos (NombreArchivo, Estado, Mensaje)
        VALUES (@ArchivoActual, 'ERROR', 'OutboundDelivery: ' + @ErrorMsg);
        
        PRINT 'ERROR CRITICO: ' + @ErrorMsg;
        RAISERROR(@ErrorMsg, 16, 1);
    END CATCH
END;
GO

-- =====================================================
-- TABLAS Y SP PARA OUTBOUND DELIVERY CONFIRM (SHP_OBDLV_CONFIRM_DECENTRAL)
-- =====================================================

-- STAGING: Tabla 1 - Cabecera
IF OBJECT_ID('dbo.Staging_EWM_OBDConfirm_Cabecera', 'U') IS NULL
BEGIN
    CREATE TABLE dbo.Staging_EWM_OBDConfirm_Cabecera (
        ID BIGINT IDENTITY(1,1) PRIMARY KEY,
        Numero_Entrega NVARCHAR(100) NOT NULL,
        Fecha_WSHDRLFDAT NVARCHAR(40),
        Fecha_WSHDRWADTI NVARCHAR(40),
        NombreArchivo NVARCHAR(1000),
        FechaCreacion DATETIME DEFAULT GETDATE()
    );
    CREATE INDEX IX_Staging_OBDConfirm_Cabecera_NumeroEntrega ON dbo.Staging_EWM_OBDConfirm_Cabecera(Numero_Entrega);
END
GO

-- STAGING: Tabla 2 - Posiciones
IF OBJECT_ID('dbo.Staging_EWM_OBDConfirm_Posiciones', 'U') IS NULL
BEGIN
    CREATE TABLE dbo.Staging_EWM_OBDConfirm_Posiciones (
        ID BIGINT IDENTITY(1,1) PRIMARY KEY,
        Numero_Entrega NVARCHAR(100) NOT NULL,
        Numero_Posicion NVARCHAR(40),
        Pedido_Ref NVARCHAR(100),
        Material_SKU NVARCHAR(200),
        Cantidad NVARCHAR(100),
        Unidad NVARCHAR(20),
        NombreArchivo NVARCHAR(1000),
        FechaCreacion DATETIME DEFAULT GETDATE()
    );
    CREATE INDEX IX_Staging_OBDConfirm_Posiciones_NumeroEntrega ON dbo.Staging_EWM_OBDConfirm_Posiciones(Numero_Entrega);
END
GO

-- STAGING: Tabla 3 - Control Posiciones
IF OBJECT_ID('dbo.Staging_EWM_OBDConfirm_Control_Posiciones', 'U') IS NULL
BEGIN
    CREATE TABLE dbo.Staging_EWM_OBDConfirm_Control_Posiciones (
        ID BIGINT IDENTITY(1,1) PRIMARY KEY,
        Numero_Entrega NVARCHAR(100) NOT NULL,
        Numero_Posicion NVARCHAR(40),
        Flag_Confirmacion NVARCHAR(20),
        NombreArchivo NVARCHAR(1000),
        FechaCreacion DATETIME DEFAULT GETDATE()
    );
    CREATE INDEX IX_Staging_OBDConfirm_Control_NumeroEntrega ON dbo.Staging_EWM_OBDConfirm_Control_Posiciones(Numero_Entrega);
END
GO

-- STAGING: Tabla 4 - Unidades Manipulacion Header
IF OBJECT_ID('dbo.Staging_EWM_OBDConfirm_Unidades_HDR', 'U') IS NULL
BEGIN
    CREATE TABLE dbo.Staging_EWM_OBDConfirm_Unidades_HDR (
        ID BIGINT IDENTITY(1,1) PRIMARY KEY,
        Numero_Entrega NVARCHAR(100),
        ID_Unidad_Manipulacion NVARCHAR(200),
        Tipo_Embalaje NVARCHAR(100),
        HU_Nivel NVARCHAR(20),
        Numero_Externo NVARCHAR(200),
        Cantidad_HU NVARCHAR(100),
        NombreArchivo NVARCHAR(1000),
        FechaCreacion DATETIME DEFAULT GETDATE()
    );
    CREATE INDEX IX_Staging_OBDConfirm_Unidades_NumeroEntrega ON dbo.Staging_EWM_OBDConfirm_Unidades_HDR(Numero_Entrega);
    CREATE INDEX IX_Staging_OBDConfirm_Unidades_HUID ON dbo.Staging_EWM_OBDConfirm_Unidades_HDR(ID_Unidad_Manipulacion);
END
GO

-- STAGING: Tabla 5 - Contenido Embalaje
IF OBJECT_ID('dbo.Staging_EWM_OBDConfirm_Contenido_Embalaje', 'U') IS NULL
BEGIN
    CREATE TABLE dbo.Staging_EWM_OBDConfirm_Contenido_Embalaje (
        ID BIGINT IDENTITY(1,1) PRIMARY KEY,
        ID_Unidad_Manipulacion_Padre NVARCHAR(200),
        ID_Unidad_Manipulacion_Hijo NVARCHAR(200),
        Numero_Entrega NVARCHAR(100),
        Numero_Posicion NVARCHAR(40),
        Cantidad_Empacada NVARCHAR(100),
        Unidad NVARCHAR(20),
        Material_SKU NVARCHAR(200),
        Nivel_HU NVARCHAR(20),
        NombreArchivo NVARCHAR(1000),
        FechaCreacion DATETIME DEFAULT GETDATE()
    );
    CREATE INDEX IX_Staging_OBDConfirm_Contenido_Padre ON dbo.Staging_EWM_OBDConfirm_Contenido_Embalaje(ID_Unidad_Manipulacion_Padre);
    CREATE INDEX IX_Staging_OBDConfirm_Contenido_NumeroEntrega ON dbo.Staging_EWM_OBDConfirm_Contenido_Embalaje(Numero_Entrega);
END
GO

-- STAGING: Tabla 6 - Extensiones
IF OBJECT_ID('dbo.Staging_EWM_OBDConfirm_Extensiones', 'U') IS NULL
BEGIN
    CREATE TABLE dbo.Staging_EWM_OBDConfirm_Extensiones (
        ID BIGINT IDENTITY(1,1) PRIMARY KEY,
        Nombre_Campo NVARCHAR(200),
        ID_Referencia NVARCHAR(200),
        Valor_1 NVARCHAR(400),
        Valor_2 NVARCHAR(400),
        Valor_3 NVARCHAR(400),
        NombreArchivo NVARCHAR(1000),
        FechaCreacion DATETIME DEFAULT GETDATE()
    );
    CREATE INDEX IX_Staging_OBDConfirm_Extensiones_Campo ON dbo.Staging_EWM_OBDConfirm_Extensiones(Nombre_Campo);
END
GO

-- TABLAS FINALES CON VERSIONADO

-- FINAL: Tabla 1 - Cabecera
IF OBJECT_ID('dbo.EWM_OBDConfirm_Cabecera', 'U') IS NULL
BEGIN
    CREATE TABLE dbo.EWM_OBDConfirm_Cabecera (
        ID INT IDENTITY(1,1) PRIMARY KEY,
        Numero_Entrega NVARCHAR(100) NOT NULL,
        Fecha_WSHDRLFDAT DATE,
        Fecha_WSHDRWADTI DATE,
        NumeroVersion INT NOT NULL,
        FechaProceso DATETIME NOT NULL DEFAULT GETDATE(),
        NombreArchivo NVARCHAR(1000)
    );
    CREATE INDEX IX_EWM_OBDConfirm_Cabecera_NumeroEntrega ON dbo.EWM_OBDConfirm_Cabecera(Numero_Entrega);
    CREATE INDEX IX_EWM_OBDConfirm_Cabecera_Version ON dbo.EWM_OBDConfirm_Cabecera(NumeroVersion DESC);
END
GO

-- FINAL: Tabla 2 - Posiciones
IF OBJECT_ID('dbo.EWM_OBDConfirm_Posiciones', 'U') IS NULL
BEGIN
    CREATE TABLE dbo.EWM_OBDConfirm_Posiciones (
        ID INT IDENTITY(1,1) PRIMARY KEY,
        Numero_Entrega NVARCHAR(100) NOT NULL,
        Numero_Posicion NVARCHAR(40),
        Pedido_Ref NVARCHAR(100),
        Material_SKU NVARCHAR(200),
        Cantidad DECIMAL(18,3),
        Unidad NVARCHAR(20),
        NumeroVersion INT NOT NULL,
        FechaProceso DATETIME NOT NULL DEFAULT GETDATE(),
        NombreArchivo NVARCHAR(1000)
    );
    CREATE INDEX IX_EWM_OBDConfirm_Posiciones_NumeroEntrega ON dbo.EWM_OBDConfirm_Posiciones(Numero_Entrega);
    CREATE INDEX IX_EWM_OBDConfirm_Posiciones_Material ON dbo.EWM_OBDConfirm_Posiciones(Material_SKU);
END
GO

-- FINAL: Tabla 3 - Control Posiciones
IF OBJECT_ID('dbo.EWM_OBDConfirm_Control_Posiciones', 'U') IS NULL
BEGIN
    CREATE TABLE dbo.EWM_OBDConfirm_Control_Posiciones (
        ID INT IDENTITY(1,1) PRIMARY KEY,
        Numero_Entrega NVARCHAR(100) NOT NULL,
        Numero_Posicion NVARCHAR(40),
        Flag_Confirmacion NVARCHAR(20),
        NumeroVersion INT NOT NULL,
        FechaProceso DATETIME NOT NULL DEFAULT GETDATE(),
        NombreArchivo NVARCHAR(1000)
    );
    CREATE INDEX IX_EWM_OBDConfirm_Control_NumeroEntrega ON dbo.EWM_OBDConfirm_Control_Posiciones(Numero_Entrega);
END
GO

-- FINAL: Tabla 4 - Unidades Manipulacion Header
IF OBJECT_ID('dbo.EWM_OBDConfirm_Unidades_HDR', 'U') IS NULL
BEGIN
    CREATE TABLE dbo.EWM_OBDConfirm_Unidades_HDR (
        ID INT IDENTITY(1,1) PRIMARY KEY,
        Numero_Entrega NVARCHAR(100) NOT NULL,
        ID_Unidad_Manipulacion NVARCHAR(200),
        Tipo_Embalaje NVARCHAR(100),
        HU_Nivel NVARCHAR(20),
        Numero_Externo NVARCHAR(200),
        Cantidad_HU DECIMAL(18,3),
        NumeroVersion INT NOT NULL,
        FechaProceso DATETIME NOT NULL DEFAULT GETDATE(),
        NombreArchivo NVARCHAR(1000)
    );
    CREATE INDEX IX_EWM_OBDConfirm_Unidades_NumeroEntrega ON dbo.EWM_OBDConfirm_Unidades_HDR(Numero_Entrega);
    CREATE INDEX IX_EWM_OBDConfirm_Unidades_HUID ON dbo.EWM_OBDConfirm_Unidades_HDR(ID_Unidad_Manipulacion);
END
GO

-- FINAL: Tabla 5 - Contenido Embalaje
IF OBJECT_ID('dbo.EWM_OBDConfirm_Contenido_Embalaje', 'U') IS NULL
BEGIN
    CREATE TABLE dbo.EWM_OBDConfirm_Contenido_Embalaje (
        ID INT IDENTITY(1,1) PRIMARY KEY,
        ID_Unidad_Manipulacion_Padre NVARCHAR(200),
        ID_Unidad_Manipulacion_Hijo NVARCHAR(200),
        Numero_Entrega NVARCHAR(100),
        Numero_Posicion NVARCHAR(40),
        Cantidad_Empacada DECIMAL(18,3),
        Unidad NVARCHAR(20),
        Material_SKU NVARCHAR(200),
        Nivel_HU NVARCHAR(20),
        NumeroVersion INT NOT NULL,
        FechaProceso DATETIME NOT NULL DEFAULT GETDATE(),
        NombreArchivo NVARCHAR(1000)
    );
    CREATE INDEX IX_EWM_OBDConfirm_Contenido_Padre ON dbo.EWM_OBDConfirm_Contenido_Embalaje(ID_Unidad_Manipulacion_Padre);
    CREATE INDEX IX_EWM_OBDConfirm_Contenido_NumeroEntrega ON dbo.EWM_OBDConfirm_Contenido_Embalaje(Numero_Entrega);
    CREATE INDEX IX_EWM_OBDConfirm_Contenido_Material ON dbo.EWM_OBDConfirm_Contenido_Embalaje(Material_SKU);
END
GO

-- FINAL: Tabla 6 - Extensiones
IF OBJECT_ID('dbo.EWM_OBDConfirm_Extensiones', 'U') IS NULL
BEGIN
    CREATE TABLE dbo.EWM_OBDConfirm_Extensiones (
        ID INT IDENTITY(1,1) PRIMARY KEY,
        Nombre_Campo NVARCHAR(200),
        ID_Referencia NVARCHAR(200),
        Valor_1 NVARCHAR(400),
        Valor_2 NVARCHAR(400),
        Valor_3 NVARCHAR(400),
        NumeroVersion INT NOT NULL,
        FechaProceso DATETIME NOT NULL DEFAULT GETDATE(),
        NombreArchivo NVARCHAR(1000)
    );
    CREATE INDEX IX_EWM_OBDConfirm_Extensiones_Campo ON dbo.EWM_OBDConfirm_Extensiones(Nombre_Campo);
    CREATE INDEX IX_EWM_OBDConfirm_Extensiones_Referencia ON dbo.EWM_OBDConfirm_Extensiones(ID_Referencia);
END
GO

-- =====================================================
-- SP PARA OUTBOUND DELIVERY CONFIRM (Con versionado + idempotencia por hash)
-- =====================================================
CREATE OR ALTER PROCEDURE sp_Procesar_OutboundDeliveryConfirm_EWM
    @ArchivoActual NVARCHAR(500)
AS
BEGIN
    SET NOCOUNT ON;
    
    -- Garantiza tabla de hash para idempotencia por archivo
    IF OBJECT_ID('dbo.EWM_OBDConfirm_FileHash', 'U') IS NULL
    BEGIN
        CREATE TABLE dbo.EWM_OBDConfirm_FileHash (
            Id INT IDENTITY(1,1) PRIMARY KEY,
            NombreArchivo NVARCHAR(1000) NOT NULL,
            HashValor VARBINARY(64) NOT NULL,
            FechaCreacion DATETIME NOT NULL DEFAULT GETDATE()
        );
        CREATE UNIQUE INDEX UX_EWM_OBDConfirm_FileHash_FileHash
            ON dbo.EWM_OBDConfirm_FileHash(NombreArchivo, HashValor);
    END;
    
    DECLARE @NumeroVersion INT;
    DECLARE @RegistrosCabecera INT = 0;
    DECLARE @RegistrosPosiciones INT = 0;
    DECLARE @RegistrosControl INT = 0;
    DECLARE @RegistrosUnidades INT = 0;
    DECLARE @RegistrosContenido INT = 0;
    DECLARE @RegistrosExtensiones INT = 0;
    DECLARE @HashActual VARBINARY(64);
    
    BEGIN TRY
        BEGIN TRANSACTION;
        
        -- 0. Calcular hash del set de staging (idempotencia por archivo)
        ;WITH TodoStaging AS (
            SELECT 'CAB' AS Tipo, Numero_Entrega, Numero_Posicion = NULL, Pedido_Ref = NULL, Material_SKU = NULL, Cantidad = NULL, Unidad = NULL, HU_Nivel = NULL, ID_Unidad_Manipulacion = NULL, Nivel_HU = NULL, ID_Referencia = NULL, Valor_1 = NULL, Valor_2 = NULL, Valor_3 = NULL
            FROM Staging_EWM_OBDConfirm_Cabecera WHERE NombreArchivo = @ArchivoActual
            UNION ALL
            SELECT 'POS', Numero_Entrega, Numero_Posicion, Pedido_Ref, Material_SKU, Cantidad, Unidad, NULL, NULL, NULL, NULL, NULL, NULL, NULL
            FROM Staging_EWM_OBDConfirm_Posiciones WHERE NombreArchivo = @ArchivoActual
            UNION ALL
            SELECT 'CTL', Numero_Entrega, Numero_Posicion, NULL, NULL, Flag_Confirmacion, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL
            FROM Staging_EWM_OBDConfirm_Control_Posiciones WHERE NombreArchivo = @ArchivoActual
            UNION ALL
            SELECT 'UNI', Numero_Entrega, NULL, NULL, NULL, Cantidad_HU, NULL, HU_Nivel, ID_Unidad_Manipulacion, NULL, NULL, NULL, NULL, NULL
            FROM Staging_EWM_OBDConfirm_Unidades_HDR WHERE NombreArchivo = @ArchivoActual
            UNION ALL
            SELECT 'CON', Numero_Entrega, Numero_Posicion, NULL, Material_SKU, Cantidad_Empacada, Unidad, Nivel_HU, NULL, ID_Unidad_Manipulacion_Padre, NULL, NULL, NULL, NULL
            FROM Staging_EWM_OBDConfirm_Contenido_Embalaje WHERE NombreArchivo = @ArchivoActual
            UNION ALL
            SELECT 'EXT', NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, ID_Referencia, Valor_1, Valor_2, Valor_3
            FROM Staging_EWM_OBDConfirm_Extensiones WHERE NombreArchivo = @ArchivoActual
        )
        SELECT @HashActual = HASHBYTES('SHA2_256', STRING_AGG(CONCAT_WS('|', Tipo, ISNULL(LTRIM(RTRIM(Numero_Entrega)), ''), ISNULL(LTRIM(RTRIM(Numero_Posicion)), ''), ISNULL(LTRIM(RTRIM(Pedido_Ref)), ''), ISNULL(LTRIM(RTRIM(Material_SKU)), ''), ISNULL(LTRIM(RTRIM(Cantidad)), ''), ISNULL(LTRIM(RTRIM(Unidad)), ''), ISNULL(LTRIM(RTRIM(HU_Nivel)), ''), ISNULL(LTRIM(RTRIM(ID_Unidad_Manipulacion)), ''), ISNULL(LTRIM(RTRIM(Nivel_HU)), ''), ISNULL(LTRIM(RTRIM(ID_Referencia)), ''), ISNULL(LTRIM(RTRIM(Valor_1)), ''), ISNULL(LTRIM(RTRIM(Valor_2)), ''), ISNULL(LTRIM(RTRIM(Valor_3)), '')), '#') WITHIN GROUP (ORDER BY Tipo, Numero_Entrega, Numero_Posicion))
        FROM TodoStaging;

        -- Si hash ya existe para este archivo, no inflar versión ni reprocesar
        IF EXISTS (SELECT 1 FROM dbo.EWM_OBDConfirm_FileHash WHERE NombreArchivo = @ArchivoActual AND HashValor = @HashActual)
        BEGIN
            PRINT '--> Archivo sin cambios, se omite reproceso: ' + @ArchivoActual;
            RETURN;
        END;

        -- 1. Determinar número de versión (global para todo el archivo)
        SELECT @NumeroVersion = ISNULL(MAX(NumeroVersion), 0) + 1
        FROM EWM_OBDConfirm_Cabecera;
        
        -- 2. Insertar CABECERA
        INSERT INTO EWM_OBDConfirm_Cabecera (
            Numero_Entrega, Fecha_WSHDRLFDAT, Fecha_WSHDRWADTI, 
            NumeroVersion, NombreArchivo
        )
        SELECT 
            LTRIM(RTRIM(Numero_Entrega)),
            TRY_CONVERT(DATE, LEFT(LTRIM(RTRIM(Fecha_WSHDRLFDAT)), 8), 112),
            TRY_CONVERT(DATE, LEFT(LTRIM(RTRIM(Fecha_WSHDRWADTI)), 8), 112),
            @NumeroVersion,
            @ArchivoActual
        FROM Staging_EWM_OBDConfirm_Cabecera
        WHERE NombreArchivo = @ArchivoActual
          AND LTRIM(RTRIM(Numero_Entrega)) <> '';
        
        SET @RegistrosCabecera = @@ROWCOUNT;
        
        -- 3. Insertar POSICIONES (Cantidad es NVARCHAR en staging, convertir)
        INSERT INTO EWM_OBDConfirm_Posiciones (
            Numero_Entrega, Numero_Posicion, Pedido_Ref, Material_SKU,
            Cantidad, Unidad, NumeroVersion, NombreArchivo
        )
        SELECT 
            LTRIM(RTRIM(Numero_Entrega)),
            LTRIM(RTRIM(Numero_Posicion)),
            LTRIM(RTRIM(Pedido_Ref)),
            LTRIM(RTRIM(Material_SKU)),
            TRY_CONVERT(DECIMAL(18,3), REPLACE(NULLIF(LTRIM(RTRIM(Cantidad)), ''), ',', '.')),
            LTRIM(RTRIM(Unidad)),
            @NumeroVersion,
            @ArchivoActual
        FROM Staging_EWM_OBDConfirm_Posiciones
        WHERE NombreArchivo = @ArchivoActual
          AND LTRIM(RTRIM(Numero_Entrega)) <> '';
        
        SET @RegistrosPosiciones = @@ROWCOUNT;
        
        -- 4. Insertar CONTROL POSICIONES
        INSERT INTO EWM_OBDConfirm_Control_Posiciones (
            Numero_Entrega, Numero_Posicion, Flag_Confirmacion,
            NumeroVersion, NombreArchivo
        )
        SELECT 
            LTRIM(RTRIM(Numero_Entrega)),
            LTRIM(RTRIM(Numero_Posicion)),
            LTRIM(RTRIM(Flag_Confirmacion)),
            @NumeroVersion,
            @ArchivoActual
        FROM Staging_EWM_OBDConfirm_Control_Posiciones
        WHERE NombreArchivo = @ArchivoActual
          AND LTRIM(RTRIM(Numero_Entrega)) <> '';
        
        SET @RegistrosControl = @@ROWCOUNT;
        
        -- 5. Insertar UNIDADES MANIPULACION (Cantidad_HU es NVARCHAR en staging)
        INSERT INTO EWM_OBDConfirm_Unidades_HDR (
            Numero_Entrega, ID_Unidad_Manipulacion, Tipo_Embalaje, HU_Nivel,
            Numero_Externo, Cantidad_HU, NumeroVersion, NombreArchivo
        )
        SELECT 
            LTRIM(RTRIM(Numero_Entrega)),
            LTRIM(RTRIM(ID_Unidad_Manipulacion)),
            LTRIM(RTRIM(Tipo_Embalaje)),
            LTRIM(RTRIM(HU_Nivel)),
            LTRIM(RTRIM(Numero_Externo)),
            TRY_CONVERT(DECIMAL(18,3), REPLACE(NULLIF(LTRIM(RTRIM(Cantidad_HU)), ''), ',', '.')),
            @NumeroVersion,
            @ArchivoActual
        FROM Staging_EWM_OBDConfirm_Unidades_HDR
        WHERE NombreArchivo = @ArchivoActual
          AND LTRIM(RTRIM(Numero_Entrega)) <> '';
        
        SET @RegistrosUnidades = @@ROWCOUNT;
        
        -- 6. Insertar CONTENIDO EMBALAJE (Cantidad_Empacada es NVARCHAR en staging)
        INSERT INTO EWM_OBDConfirm_Contenido_Embalaje (
            ID_Unidad_Manipulacion_Padre, ID_Unidad_Manipulacion_Hijo,
            Numero_Entrega, Numero_Posicion, Cantidad_Empacada, Unidad,
            Material_SKU, Nivel_HU, NumeroVersion, NombreArchivo
        )
        SELECT 
            LTRIM(RTRIM(ID_Unidad_Manipulacion_Padre)),
            LTRIM(RTRIM(ID_Unidad_Manipulacion_Hijo)),
            LTRIM(RTRIM(Numero_Entrega)),
            LTRIM(RTRIM(Numero_Posicion)),
            TRY_CONVERT(DECIMAL(18,3), REPLACE(NULLIF(LTRIM(RTRIM(Cantidad_Empacada)), ''), ',', '.')),
            LTRIM(RTRIM(Unidad)),
            LTRIM(RTRIM(Material_SKU)),
            LTRIM(RTRIM(Nivel_HU)),
            @NumeroVersion,
            @ArchivoActual
        FROM Staging_EWM_OBDConfirm_Contenido_Embalaje
        WHERE NombreArchivo = @ArchivoActual;
        
        SET @RegistrosContenido = @@ROWCOUNT;
        
        -- 7. Insertar EXTENSIONES
        INSERT INTO EWM_OBDConfirm_Extensiones (
            Nombre_Campo, ID_Referencia, Valor_1, Valor_2, Valor_3,
            NumeroVersion, NombreArchivo
        )
        SELECT 
            LTRIM(RTRIM(Nombre_Campo)),
            LTRIM(RTRIM(ID_Referencia)),
            LTRIM(RTRIM(Valor_1)),
            LTRIM(RTRIM(Valor_2)),
            LTRIM(RTRIM(Valor_3)),
            @NumeroVersion,
            @ArchivoActual
        FROM Staging_EWM_OBDConfirm_Extensiones
        WHERE NombreArchivo = @ArchivoActual;
        
        SET @RegistrosExtensiones = @@ROWCOUNT;
        
        -- 8. Registrar hash del archivo procesado (para idempotencia futura)
        INSERT INTO dbo.EWM_OBDConfirm_FileHash (NombreArchivo, HashValor)
        VALUES (@ArchivoActual, @HashActual);
        
        -- 9. Registrar en bitácora
        INSERT INTO BitacoraArchivos (NombreArchivo, Estado, Mensaje)
        VALUES (
            @ArchivoActual, 
            'PROCESADO', 
            'OBDConfirm - Cab:' + CAST(@RegistrosCabecera AS NVARCHAR) + 
            ' | Pos:' + CAST(@RegistrosPosiciones AS NVARCHAR) + 
            ' | Ctrl:' + CAST(@RegistrosControl AS NVARCHAR) + 
            ' | Units:' + CAST(@RegistrosUnidades AS NVARCHAR) + 
            ' | Cont:' + CAST(@RegistrosContenido AS NVARCHAR) + 
            ' | Ext:' + CAST(@RegistrosExtensiones AS NVARCHAR) + 
            ' | Ver:' + CAST(@NumeroVersion AS NVARCHAR)
        );
        
        -- 10. Limpiar staging
        DELETE FROM Staging_EWM_OBDConfirm_Cabecera WHERE NombreArchivo = @ArchivoActual;
        DELETE FROM Staging_EWM_OBDConfirm_Posiciones WHERE NombreArchivo = @ArchivoActual;
        DELETE FROM Staging_EWM_OBDConfirm_Control_Posiciones WHERE NombreArchivo = @ArchivoActual;
        DELETE FROM Staging_EWM_OBDConfirm_Unidades_HDR WHERE NombreArchivo = @ArchivoActual;
        DELETE FROM Staging_EWM_OBDConfirm_Contenido_Embalaje WHERE NombreArchivo = @ArchivoActual;
        DELETE FROM Staging_EWM_OBDConfirm_Extensiones WHERE NombreArchivo = @ArchivoActual;
        
        COMMIT TRANSACTION;
        
        PRINT '--> [VERSIONADO] OutboundDeliveryConfirm procesado: ' + @ArchivoActual;
        PRINT '    Cabecera: ' + CAST(@RegistrosCabecera AS NVARCHAR);
        PRINT '    Posiciones: ' + CAST(@RegistrosPosiciones AS NVARCHAR);
        PRINT '    Control: ' + CAST(@RegistrosControl AS NVARCHAR);
        PRINT '    Unidades: ' + CAST(@RegistrosUnidades AS NVARCHAR);
        PRINT '    Contenido: ' + CAST(@RegistrosContenido AS NVARCHAR);
        PRINT '    Extensiones: ' + CAST(@RegistrosExtensiones AS NVARCHAR);
        PRINT '    Version: ' + CAST(@NumeroVersion AS NVARCHAR);
        
    END TRY
    BEGIN CATCH
        IF @@TRANCOUNT > 0
            ROLLBACK TRANSACTION;
        
        DECLARE @ErrorMsg NVARCHAR(4000) = ERROR_MESSAGE();
        
        -- Registrar error en bitácora
        INSERT INTO BitacoraArchivos (NombreArchivo, Estado, Mensaje)
        VALUES (@ArchivoActual, 'ERROR', 'OBDConfirm: ' + @ErrorMsg);
        
        PRINT 'ERROR CRITICO: ' + @ErrorMsg;
        RAISERROR(@ErrorMsg, 16, 1);
    END CATCH
END;
GO

PRINT '=============================================';
PRINT 'SCHEMA COMPLETO CREADO EXITOSAMENTE';
PRINT '=============================================';
PRINT '';
PRINT 'TABLAS DE STAGING (11):';
PRINT '  - BitacoraArchivos';
PRINT '  - Staging_EWM_Cartoning';
PRINT '  - Staging_EWM_WaveConfirm';
PRINT '  - Staging_EWM_OutboundDelivery_Header';
PRINT '  - Staging_EWM_OutboundDelivery_Items';
PRINT '  - Staging_EWM_OBDConfirm_Cabecera';
PRINT '  - Staging_EWM_OBDConfirm_Posiciones';
PRINT '  - Staging_EWM_OBDConfirm_Control_Posiciones';
PRINT '  - Staging_EWM_OBDConfirm_Unidades_HDR';
PRINT '  - Staging_EWM_OBDConfirm_Contenido_Embalaje';
PRINT '  - Staging_EWM_OBDConfirm_Extensiones';
PRINT '';
PRINT 'TABLAS FINALES (13):';
PRINT '  - EWM_Pedidos (Cartoning)';
PRINT '  - EWM_Cajas (Cartoning)';
PRINT '  - EWM_Items (Cartoning)';
PRINT '  - EWM_WaveConfirm';
PRINT '  - EWM_OutboundDelivery_Header';
PRINT '  - EWM_OutboundDelivery_Items';
PRINT '  - EWM_OBDConfirm_Cabecera';
PRINT '  - EWM_OBDConfirm_Posiciones';
PRINT '  - EWM_OBDConfirm_Control_Posiciones';
PRINT '  - EWM_OBDConfirm_Unidades_HDR';
PRINT '  - EWM_OBDConfirm_Contenido_Embalaje';
PRINT '  - EWM_OBDConfirm_Extensiones';
PRINT '';
PRINT 'STORED PROCEDURES (4):';
PRINT '  - sp_Procesar_Cartoning_EWM';
PRINT '  - sp_Procesar_WaveConfirm_EWM';
PRINT '  - sp_Procesar_OutboundDelivery_EWM';
PRINT '  - sp_Procesar_OutboundDeliveryConfirm_EWM';
PRINT '';
PRINT 'Todas las tablas incluyen versionado automatico';
PRINT '=============================================';
