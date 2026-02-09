USE [OPS_OrquestaFact]
GO
/****** Object:  StoredProcedure [dbo].[sp_Procesar_OutboundDelivery_EWM]    Script Date: 09-02-2026 16:50:54 ******/
SET ANSI_NULLS ON
GO
SET QUOTED_IDENTIFIER ON
GO


-- =====================================================
-- SP PARA OUTBOUND DELIVERY (Con versionado)
-- =====================================================
ALTER   PROCEDURE [dbo].[sp_Procesar_OutboundDelivery_EWM]
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
