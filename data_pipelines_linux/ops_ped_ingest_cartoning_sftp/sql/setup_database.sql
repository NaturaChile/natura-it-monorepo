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

-- =============================================
-- 2. TABLAS DEL MODELO DE NEGOCIO (Inferidas de tus SPs)
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

-- =============================================
-- 3. STORED PROCEDURES (Tus versiones originales)
-- =============================================

-- SP AVANZADO (El que usaremos en el Bot)
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