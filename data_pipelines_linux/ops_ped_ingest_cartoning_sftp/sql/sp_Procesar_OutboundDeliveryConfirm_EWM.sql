USE [OPS_OrquestaFact]
GO
/****** Object:  StoredProcedure [dbo].[sp_Procesar_OutboundDeliveryConfirm_EWM]    Script Date: 09-02-2026 16:50:42 ******/
SET ANSI_NULLS ON
GO
SET QUOTED_IDENTIFIER ON
GO


CREATE OR ALTER PROCEDURE [dbo].[sp_Procesar_OutboundDeliveryConfirm_EWM]
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
            -- Convertir YYYYMMDDHHMMSS (14 chars) a DATE usando solo los primeros 8 chars
            TRY_CONVERT(DATE, LEFT(LTRIM(RTRIM(Fecha_WSHDRLFDAT)), 8), 112),
            TRY_CONVERT(DATE, LEFT(LTRIM(RTRIM(Fecha_WSHDRWADTI)), 8), 112),
            @NumeroVersion,
            @ArchivoActual
        FROM Staging_EWM_OBDConfirm_Cabecera
        WHERE NombreArchivo = @ArchivoActual
          AND LTRIM(RTRIM(Numero_Entrega)) <> '';
        
        SET @RegistrosCabecera = @@ROWCOUNT;
        
        -- 3. Insertar POSICIONES
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
        
        -- 5. Insertar UNIDADES MANIPULACION
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
        
        -- 6. Insertar CONTENIDO EMBALAJE
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
        
        -- 8.1 Registrar hash del archivo procesado (para idempotencia futura)
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
