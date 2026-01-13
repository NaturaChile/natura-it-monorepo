-- =====================================================
-- ACTUALIZACIÓN PARA WAVECONFIRM CON VERSIONADO
-- Ejecuta este script en tu base de datos
-- =====================================================

USE OPS_OrquestaFact;
GO

PRINT '=============================================='
PRINT 'INICIANDO ACTUALIZACIÓN WAVECONFIRM'
PRINT '=============================================='
PRINT ''

-- =====================================================
-- 1. TABLA FINAL CON VERSIONADO
-- =====================================================
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
    
    CREATE INDEX IX_WaveConfirm_WaveID ON dbo.EWM_WaveConfirm(WaveID);
    CREATE INDEX IX_WaveConfirm_PedidoID ON dbo.EWM_WaveConfirm(PedidoID);
    CREATE INDEX IX_WaveConfirm_CajaID ON dbo.EWM_WaveConfirm(CajaID);
    CREATE INDEX IX_WaveConfirm_Composite ON dbo.EWM_WaveConfirm(WaveID, PedidoID, CajaID);
    
    PRINT '[OK] Tabla EWM_WaveConfirm creada con versionado'
END
ELSE
BEGIN
    PRINT '[INFO] Tabla EWM_WaveConfirm ya existe'
END
GO

-- =====================================================
-- 2. STORED PROCEDURE CON VERSIONADO COMPLETO
-- =====================================================
PRINT ''
PRINT 'Creando/Actualizando SP sp_Procesar_WaveConfirm_EWM...'
GO

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
        
        -- 1. LIMPIEZA Y VALIDACIÓN
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
            PRINT '    Registros descartados: ' + CAST(@Descartados AS VARCHAR(10));
        
        UPDATE Staging_EWM_WaveConfirm
        SET WaveID = LTRIM(RTRIM(WaveID)),
            PedidoID = LTRIM(RTRIM(PedidoID)),
            CajaID = LTRIM(RTRIM(CajaID))
        WHERE NombreArchivo = @ArchivoActual AND Procesado = 0;
        
        -- 2. TABLA TEMPORAL PARA VERSIONADO
        CREATE TABLE #TempWaveConfirm (
            WaveID VARCHAR(50),
            PedidoID VARCHAR(50),
            CajaID VARCHAR(100),
            NombreArchivo VARCHAR(255),
            VersionAnterior INT
        );
        
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
            )
        FROM Staging_EWM_WaveConfirm s
        WHERE s.NombreArchivo = @ArchivoActual AND s.Procesado = 0;
        
        DECLARE @Procesados INT = @@ROWCOUNT;
        DECLARE @Nuevos INT, @Actualizaciones INT;
        
        SELECT @Nuevos = COUNT(*) FROM #TempWaveConfirm WHERE VersionAnterior = 0;
        SELECT @Actualizaciones = COUNT(*) FROM #TempWaveConfirm WHERE VersionAnterior > 0;
        
        PRINT '    Nuevos: ' + CAST(@Nuevos AS VARCHAR(10)) + 
              ', Actualizaciones: ' + CAST(@Actualizaciones AS VARCHAR(10));
        
        -- 3. INSERTAR CON VERSIONADO
        INSERT INTO EWM_WaveConfirm (WaveID, PedidoID, CajaID, NombreArchivo, NumeroVersion, FechaProceso)
        SELECT 
            WaveID, PedidoID, CajaID, NombreArchivo,
            VersionAnterior + 1,
            GETDATE()
        FROM #TempWaveConfirm;
        
        -- 4. LIMPIEZA
        DROP TABLE #TempWaveConfirm;
        
        UPDATE Staging_EWM_WaveConfirm
        SET Procesado = 1
        WHERE NombreArchivo = @ArchivoActual;
        
        DELETE FROM Staging_EWM_WaveConfirm WHERE NombreArchivo = @ArchivoActual;
        
        INSERT INTO BitacoraArchivos (NombreArchivo, Estado, Mensaje)
        VALUES (
            @ArchivoActual, 
            'PROCESADO', 
            'WaveConfirm: ' + CAST(@Nuevos AS VARCHAR(10)) + ' nuevos, ' + 
            CAST(@Actualizaciones AS VARCHAR(10)) + ' actualizaciones'
        );
        
        COMMIT TRANSACTION;
        PRINT '--> [VERSIONADO] Archivo procesado: ' + @ArchivoActual;
        
    END TRY
    BEGIN CATCH
        IF @@TRANCOUNT > 0 ROLLBACK TRANSACTION;
        DROP TABLE IF EXISTS #TempWaveConfirm;
            
        DECLARE @ErrorMessage NVARCHAR(4000) = ERROR_MESSAGE();
        
        INSERT INTO BitacoraArchivos (NombreArchivo, Estado, Mensaje)
        VALUES (@ArchivoActual, 'ERROR', 'WaveConfirm: ' + @ErrorMessage);
        
        PRINT 'ERROR CRITICO: ' + @ErrorMessage;
        RAISERROR(@ErrorMessage, 16, 1);
    END CATCH
END
GO

PRINT '[OK] SP sp_Procesar_WaveConfirm_EWM actualizado'
PRINT ''
PRINT '=============================================='
PRINT 'ACTUALIZACIÓN COMPLETADA'
PRINT '=============================================='
PRINT 'Tabla: EWM_WaveConfirm (con versionado)'
PRINT 'SP: sp_Procesar_WaveConfirm_EWM (completo)'
PRINT 'Bitácora: Integrada'
PRINT ''
PRINT 'Sistema listo para procesar WaveConfirm'
PRINT '=============================================='
