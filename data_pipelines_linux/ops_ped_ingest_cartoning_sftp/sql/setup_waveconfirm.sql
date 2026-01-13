-- =====================================================
-- ACTUALIZACIÓN SQL PARA MULTI-SOURCE PIPELINE
-- Ejecuta este script en tu base de datos
-- =====================================================

USE [TuBaseDeDatos]  -- Cambia por tu base de datos
GO

-- =====================================================
-- TABLA STAGING PARA WAVECONFIRM
-- =====================================================
IF NOT EXISTS (SELECT * FROM sys.tables WHERE name = 'Staging_EWM_WaveConfirm')
BEGIN
    CREATE TABLE Staging_EWM_WaveConfirm (
        ID BIGINT IDENTITY(1,1) PRIMARY KEY,
        WaveID VARCHAR(50),
        PedidoID VARCHAR(50),
        columna0 VARCHAR(50),
        CajaID VARCHAR(100),
        NombreArchivo VARCHAR(255),
        FechaIngesta DATETIME DEFAULT GETDATE(),
        Procesado BIT DEFAULT 0
    )
    
    CREATE INDEX IX_WaveConfirm_Procesado ON Staging_EWM_WaveConfirm(Procesado, FechaIngesta)
    CREATE INDEX IX_WaveConfirm_Archivo ON Staging_EWM_WaveConfirm(NombreArchivo)
    CREATE INDEX IX_WaveConfirm_WaveID ON Staging_EWM_WaveConfirm(WaveID)
    
    PRINT 'Tabla Staging_EWM_WaveConfirm creada exitosamente'
END
ELSE
BEGIN
    PRINT 'Tabla Staging_EWM_WaveConfirm ya existe'
END
GO

-- =====================================================
-- STORED PROCEDURE PARA PROCESAR WAVECONFIRM
-- =====================================================
CREATE OR ALTER PROCEDURE sp_Procesar_WaveConfirm_EWM
    @ArchivoActual VARCHAR(255)
AS
BEGIN
    SET NOCOUNT ON;
    
    BEGIN TRY
        BEGIN TRANSACTION;
        
        -- ========================================================
        -- AQUÍ VA TU LÓGICA DE TRANSFORMACIÓN Y LIMPIEZA
        -- ========================================================
        
        -- EJEMPLO BÁSICO: Validaciones y limpieza
        DECLARE @TotalRegistros INT;
        SELECT @TotalRegistros = COUNT(*) 
        FROM Staging_EWM_WaveConfirm 
        WHERE NombreArchivo = @ArchivoActual AND Procesado = 0;
        
        PRINT 'Procesando ' + CAST(@TotalRegistros AS VARCHAR(10)) + ' registros de ' + @ArchivoActual;
        
        -- OPCIÓN 1: Insertar en tabla final
        -- INSERT INTO TuTablaFinal_WaveConfirm (WaveID, PedidoID, CajaID, FechaIngesta, Archivo)
        -- SELECT 
        --     WaveID,
        --     PedidoID,
        --     CajaID,
        --     FechaIngesta,
        --     NombreArchivo
        -- FROM Staging_EWM_WaveConfirm
        -- WHERE NombreArchivo = @ArchivoActual 
        --   AND Procesado = 0
        --   AND WaveID IS NOT NULL  -- Validación básica
        --   AND CajaID IS NOT NULL
        
        -- OPCIÓN 2: Hacer UPDATE en tablas existentes
        -- UPDATE TuTablaExistente
        -- SET EstadoWave = 'CONFIRMADO',
        --     FechaConfirmacion = GETDATE()
        -- FROM TuTablaExistente t
        -- INNER JOIN Staging_EWM_WaveConfirm s ON t.WaveID = s.WaveID AND t.PedidoID = s.PedidoID
        -- WHERE s.NombreArchivo = @ArchivoActual AND s.Procesado = 0
        
        -- Marcar registros del archivo como procesados
        UPDATE Staging_EWM_WaveConfirm
        SET Procesado = 1
        WHERE NombreArchivo = @ArchivoActual;
        
        COMMIT TRANSACTION;
        
        PRINT 'Archivo ' + @ArchivoActual + ' procesado exitosamente';
        
    END TRY
    BEGIN CATCH
        IF @@TRANCOUNT > 0
            ROLLBACK TRANSACTION;
            
        DECLARE @ErrorMessage NVARCHAR(4000) = ERROR_MESSAGE();
        DECLARE @ErrorLine INT = ERROR_LINE();
        
        RAISERROR('ERROR en sp_Procesar_WaveConfirm_EWM (Línea %d): %s', 16, 1, @ErrorLine, @ErrorMessage);
    END CATCH
END
GO

PRINT ''
PRINT '=============================================='
PRINT 'INSTALACIÓN COMPLETADA'
PRINT '=============================================='
PRINT 'Tabla creada: Staging_EWM_WaveConfirm'
PRINT 'SP creado: sp_Procesar_WaveConfirm_EWM'
PRINT ''
PRINT 'IMPORTANTE: Debes completar la lógica de negocio'
PRINT 'dentro del SP según tus requerimientos.'
PRINT '=============================================='
