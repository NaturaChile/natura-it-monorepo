USE [OPS_OrquestaFact]
GO
/****** Object:  StoredProcedure [dbo].[sp_Procesar_Cartoning_EWM]    Script Date: 09-02-2026 16:51:25 ******/
SET ANSI_NULLS ON
GO
SET QUOTED_IDENTIFIER ON
GO


-- =============================================
-- 3. STORED PROCEDURES
-- =============================================

-- =====================================================
-- SP PARA CARTONING (Con versionado)
-- =====================================================
ALTER   PROCEDURE [dbo].[sp_Procesar_Cartoning_EWM]
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
