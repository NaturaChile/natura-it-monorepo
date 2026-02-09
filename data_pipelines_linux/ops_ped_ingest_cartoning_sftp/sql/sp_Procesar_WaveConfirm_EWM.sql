USE [OPS_OrquestaFact]
GO
/****** Object:  StoredProcedure [dbo].[sp_Procesar_WaveConfirm_EWM]    Script Date: 09-02-2026 16:49:45 ******/
SET ANSI_NULLS ON
GO
SET QUOTED_IDENTIFIER ON
GO


-- =====================================================
-- SP PARA WAVECONFIRM (Con versionado)
-- =====================================================
ALTER   PROCEDURE [dbo].[sp_Procesar_WaveConfirm_EWM]
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
